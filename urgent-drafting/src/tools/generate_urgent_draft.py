"""Main tool for generating urgent news drafts with human-in-the-loop

This tool implements the exact flow from the original LangGraph implementation:
1. Retrieve assets (all included by default)
2. Generate urgent
3. Review loop (regenerate/refine/approve)
"""

from mcp_hitl import resumable, interrupt
from typing import Dict, Any
import logging

from .base import BaseTool
from ..models import ToolResult
from shared.llm import LLMOrchestratorFactory
from ..config.llm_skill_config import load_llm_config
from ..services.intent_interpreter import IntentInterpreter
from .urgent_helpers import format_urgent_sources
from .urgent_actions import (
    generate_urgent_content,
    handle_refinement,
    handle_regeneration,
    retrieve_and_prepare_assets,
    apply_asset_reordering,
)
from .urgent_actions.constants import (
    ACTION_APPROVE,
    ACTION_INSERT,
    ACTION_REGENERATE,
    ACTION_REFINE,
    ACTION_CANCEL,
    INTERRUPT_TYPE_REVIEW,
)

logger = logging.getLogger(__name__)


class GenerateUrgentDraftTool(BaseTool):
    """Main tool for generating urgent news drafts - matches LangGraph flow exactly"""

    @property
    def name(self) -> str:
        return "generate_urgent_draft"

    @property
    def description(self) -> str:
        return (
            "Generate an urgent news draft from alerts/flashes. "
            "Interactive workflow with generation, review, and refinement. "
            "Supports USN or keyword search for finding news flashes. "
            "When an asset ID or headline is provided from page context, the matching alert becomes the lead alert. "
            "Priority: asset ID match first, then headline match if asset ID not provided."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "usn": {
                "type": "string",
                "description": "Pre-selected USN from context. You always must pass this parameter. Example format: EMQ8BGO4Q",
                "required": True
            },
            "asset_id": {
                "type": "string",
                "description": "Asset ID from context. When provided, this asset becomes the lead alert in the urgent draft. You must pass this parameter if it is provided in the context. Format is uuid'",
                "required": False
            },
            "headline": {
                "type": "string",
                "description": "Headline from the open story in the page context. When provided, the system will prioritize the alert that matches this headline. You must pass this parameter if it is provided in the context.",
                "required": False
            }
        }

    @property
    def response_mode(self) -> str:
        return "direct"  # Return direct response without orchestrator interpretation

    def _error_response(self, message: str, is_error: bool = True) -> ToolResult:
        """
        Create a consistent error/info response.

        Args:
            message: Message to return to user
            is_error: Whether this is an error (True) or info message (False)

        Returns:
            ToolResult with the message
        """
        return ToolResult(
            content=[{"type": "text", "text": message}],
            isError=is_error
        )

    # Delegate methods - these wrap the modular functions to work with @resumable decorator
    # The decorator needs these to be instance methods to properly cache their results

    async def _retrieve_and_prepare_assets(self, usn: str, jwt_token: str):
        return await retrieve_and_prepare_assets(usn, jwt_token)

    async def _generate_urgent_content(self, assets, llm):
        return await generate_urgent_content(assets, llm)

    def _apply_asset_reordering(self, assets, asset_id, headline=None):
        return apply_asset_reordering(assets, asset_id, headline)

    def _handle_regeneration(self, feedback, original_assets):
        return handle_regeneration(feedback, original_assets)

    async def _handle_refinement(self, feedback, current_headline, current_body, assets, llm):
        return await handle_refinement(feedback, current_headline, current_body, assets, llm)

    @resumable
    async def execute(self, arguments: Dict[str, Any], jwt_token: str) -> ToolResult:
        """
        Execute urgent draft generation - EXACT LangGraph flow:
        1. Retrieve assets (all included by default)
        2. Generate urgent
        3. Review loop (regenerate/refine/approve)

        CRITICAL: Every change (generate/regenerate/refine) MUST be followed by review.
        """
        # Initialize services
        llm_config = load_llm_config()
        llm = LLMOrchestratorFactory.create(llm_config)
        interpreter = IntentInterpreter(llm)

        # Validate input
        usn = arguments.get("usn")
        if not usn:
            return self._error_response("No query or USN provided")

        # Retrieve and prepare assets
        try:
            selectable_assets, selectable_assets_original = await self._retrieve_and_prepare_assets(usn, jwt_token)
        except Exception as e:
            logger.error(f"Failed to retrieve assets: {str(e)}")
            return self._error_response(f"Failed to retrieve assets: {str(e)}")

        # Initialize state
        current_headline = None
        current_body = None
        current_urgent = None
        lead_asset_id = None
        is_first_generation = True  # Track if this is the first generation

        # Main workflow loop - continues until user approves
        while True:
            # Generate if needed
            if current_urgent is None:
                # Apply asset_id/headline reordering ONLY on first generation
                # After user reorders and regenerates, respect their ordering
                if is_first_generation:
                    self._apply_asset_reordering(
                        selectable_assets,
                        arguments.get("asset_id"),
                        arguments.get("headline")
                    )
                    is_first_generation = False  # Mark first generation as complete

                # Check if any assets are included
                included = [a for a in selectable_assets if a.included]
                if not included:
                    logger.error("No assets selected for generation")
                    return self._error_response("No news flashes selected for generation")

                logger.info(f"Generating urgent from {len(included)}/{len(selectable_assets)} assets")
                lead_asset_id = included[0].id

                # Generate urgent content
                try:
                    current_headline, current_body, current_urgent = await self._generate_urgent_content(
                        selectable_assets, llm
                    )
                    logger.info("Generation successful")
                except Exception as e:
                    logger.error(f"Generation failed: {str(e)}")
                    return self._error_response(f"Generation failed: {str(e)}")

            # Add sources for display
            urgent_with_sources = format_urgent_sources(current_urgent, selectable_assets)

            # REVIEW INTERRUPT - Core of the workflow
            logger.info("Requesting urgent review from user")

            review_raw = interrupt({
                "type": INTERRUPT_TYPE_REVIEW,
                "message": "Review the generated urgent and choose an action",
                "context": {
                    "content": current_urgent,
                    "asset_id": lead_asset_id,
                    "assets": [a.model_dump() for a in selectable_assets]
                }
            })

            # Interpret the user's natural language response
            review_feedback = await interpreter.interpret_review_response(
                review_raw,
                {
                    "urgent": current_urgent,
                    "assets": selectable_assets,
                    "headline": current_headline,
                    "body": current_body
                }
            )

            action = review_feedback.get("action")
            logger.info(f"User action: {action}")

            # Handle user actions
            if action in [ACTION_APPROVE, ACTION_INSERT]:
                logger.info("Urgent approved by user")
                return ToolResult(
                    content=[{"type": "text", "text": urgent_with_sources}],
                    isError=False
                )

            elif action == ACTION_REGENERATE:
                logger.info("User requested regeneration")

                # Update asset selection if provided
                new_assets = self._handle_regeneration(review_feedback, selectable_assets_original)
                if new_assets:
                    selectable_assets = new_assets

                # Clear state to force regeneration
                current_urgent = None
                current_headline = None
                current_body = None

            elif action == ACTION_REFINE:
                logger.info("User requested refinement")

                # Handle refinement
                refined_headline, refined_body, refined_urgent = await self._handle_refinement(
                    review_feedback,
                    current_headline,
                    current_body,
                    selectable_assets,
                    llm
                )

                # Update state if refinement succeeded
                if refined_urgent:
                    current_headline = refined_headline
                    current_body = refined_body
                    current_urgent = refined_urgent

            elif action == ACTION_CANCEL:
                logger.info("User cancelled the workflow")
                return self._error_response("Urgent drafting cancelled by user", is_error=False)

            else:
                # Unknown action - treat as refinement request
                logger.warning(f"Unknown action '{action}', treating as refinement")

                # Import refine_urgent_content for unknown actions
                from .urgent_actions.refine import refine_urgent_content

                try:
                    current_headline, current_body, current_urgent = await refine_urgent_content(
                        current_headline,
                        current_body,
                        str(review_raw),
                        selectable_assets,
                        llm
                    )
                except Exception as e:
                    logger.error(f"Refinement failed: {str(e)}")
