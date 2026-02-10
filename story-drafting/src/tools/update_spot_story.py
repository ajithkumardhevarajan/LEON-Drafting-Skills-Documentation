"""
Update Spot Story Tool

This tool updates existing spot stories by integrating new information.
Supports two modes: add_background (preserve lede) and story_rewrite (new lede).
Implements the full workflow with human-in-the-loop review.
"""

from typing import Any, Dict, Optional, List
import logging
from mcp_hitl import resumable, interrupt

from .base import BaseTool
from ..models import ToolResult, Asset
from ..services import get_llm_orchestrator, get_intent_interpreter
from .spot_story_actions import (
    fetch_existing_story,
    select_update_mode,
    generate_updated_spot_story_content,
    search_archive_assets,
    handle_asset_selection,
    refine_story_content,
    ACTION_APPROVE,
    ACTION_REGENERATE,
    ACTION_REFINE,
    ACTION_CANCEL,
    INTERRUPT_TYPE_REVIEW,
    UpdateMode,
)

logger = logging.getLogger(__name__)


class UpdateSpotStoryTool(BaseTool):
    """
    Tool for updating existing spot stories with new information.

    This tool implements the full story update workflow:
    1. Fetch existing story by USN
    2. Prompt user for update mode selection
    3. Optionally search archive for background sources
    4. Generate updated story
    5. Present for review (interrupt)
    6. Handle user feedback (approve/refine/regenerate/cancel)
    """

    @property
    def name(self) -> str:
        return "update_spot_story"

    @property
    def description(self) -> str:
        return (
            "Update an existing Reuters spot story with new information. "
            "The tool interprets the user's natural language request to extract the USN and new content. "
            "Supports 'add_background' (preserve lede) or 'story_rewrite' (new lede) modes. "
            "Interactive workflow with generation, review, and refinement."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "request": {
                "type": "string",
                "description": (
                    "The user's natural language request for updating a spot story. "
                    "Must include the USN of the story to update and the new information to add. "
                    "Example: 'Update story LXN3VG03Q with new info that the deal closes in Q1'"
                ),
                "required": True
            }
        }

    @property
    def response_mode(self) -> str:
        return "direct"

    @property
    def orchestration_hints(self) -> Dict[str, Any]:
        """
        Fast-path routing hints to bypass LLM tool selection.

        When user input matches these patterns (especially with USN),
        route directly to this tool without LLM decision - saves ~1-2s latency.
        """
        return {
            "enabled": True,
            "priority": 5,
            "query_patterns": [
                # Case-insensitive patterns - USN format: alphanumeric 6-12 chars
                r"(?:update|rewrite)\s+(?:the\s+)?story\s+[A-Z0-9]{6,12}",
                r"(?:update|rewrite)\s+(?:the\s+)?USN\s+[A-Z0-9]{6,12}",
                r"(?:add|include)\s+(?:new\s+)?(?:info|information|background)\s+(?:to\s+)?(?:story\s+)?[A-Z0-9]{6,12}",
                r"[A-Z0-9]{6,12}\s+(?:update|rewrite|add)",
            ],
            "parameter_extractions": [
                {
                    "parameter_name": "request",
                    "jsonpath": None,
                    "fallback": "user_query",
                    "required": True,
                    "default": None
                }
            ],
            "description": "Handles spot story update requests with USN"
        }

    def _error_response(self, message: str, is_error: bool = True) -> ToolResult:
        """Create a consistent error/info response."""
        return ToolResult(
            content=[{"type": "text", "text": message}],
            isError=is_error
        )

    # Delegate methods for @resumable decorator caching

    async def _fetch_story(self, jwt_token: str, usn: str) -> Optional[Asset]:
        return await fetch_existing_story(jwt_token, usn)

    def _select_update_mode(self) -> UpdateMode:
        return select_update_mode()

    async def _search_archive(self, jwt_token: str, query: str) -> List[Asset]:
        return await search_archive_assets(jwt_token, query)

    def _handle_asset_selection(self, assets: List[Asset]) -> List[Asset]:
        return handle_asset_selection(assets)

    async def _generate_updated_story(
        self,
        existing_story: Asset,
        new_content_sources: str,
        update_mode: UpdateMode,
        background_assets: List[Asset],
        llm
    ):
        return await generate_updated_spot_story_content(
            existing_story, new_content_sources, update_mode, background_assets, llm
        )

    async def _refine_story(
        self,
        story_draft: str,
        instructions: str,
        llm
    ) -> str:
        return await refine_story_content(story_draft, instructions, llm)

    @resumable
    async def execute(
        self,
        arguments: Dict[str, Any],
        jwt_token: Optional[str] = None
    ) -> ToolResult:
        """
        Execute story update workflow.

        1. Fetch existing story by USN
        2. Prompt for update mode selection
        3. Optionally search archive for background sources
        4. Generate updated story
        5. Present for review (interrupt)
        6. Handle user feedback (approve/refine/regenerate/cancel)
        """
        # Initialize services
        llm = get_llm_orchestrator()
        interpreter = get_intent_interpreter()

        # Debug: log received arguments
        logger.info(f"Received arguments: {arguments}")
        logger.info(f"Arguments keys: {list(arguments.keys())}")

        # Extract user request - accept multiple common parameter names from backend
        user_request = (
            arguments.get("request") or
            arguments.get("content") or
            arguments.get("user_request") or
            arguments.get("message") or
            arguments.get("query") or
            arguments.get("input") or
            ""
        )

        if not user_request:
            return self._error_response(
                f"No user request provided. Received keys: {list(arguments.keys())}"
            )

        # Use intent interpreter to extract structured parameters from the request
        try:
            logger.info(f"Interpreting user request: {user_request[:100]}...")
            extracted = await interpreter.interpret_story_update_request(user_request)

            usn = extracted.usn
            new_content_sources = extracted.new_content
            use_archive = extracted.use_archive
            archive_query = extracted.archive_query or ""

            logger.info(
                f"Extracted parameters - usn: {usn}, "
                f"use_archive: {use_archive}, "
                f"archive_query: {archive_query}, "
                f"content_length: {len(new_content_sources)}"
            )

        except Exception as e:
            logger.error(f"Failed to interpret request: {e}")
            return self._error_response(f"Failed to understand request: {str(e)}")

        if not usn:
            return self._error_response("Could not extract USN from request. Please specify the story USN to update.")

        if not new_content_sources:
            return self._error_response("Could not extract new content from request. Please specify what to update.")

        if not jwt_token:
            return self._error_response("Authentication token is required")

        # Step 1: Fetch existing story
        logger.info(f"Fetching existing story with USN: {usn}")

        try:
            existing_story = await self._fetch_story(jwt_token, usn)

            if not existing_story:
                return self._error_response(f"No story found with USN: {usn}")

            logger.info(f"Found story: {existing_story.headline[:50]}...")

        except Exception as e:
            logger.error(f"Failed to fetch story: {str(e)}")
            return self._error_response(f"Failed to fetch story: {str(e)}")

        # Step 2: Select update mode
        logger.info("Requesting update mode selection from user")
        update_mode = self._select_update_mode()
        logger.info(f"Selected update mode: {update_mode}")

        # Step 3: Archive search if requested
        background_assets: List[Asset] = []

        if use_archive and archive_query:
            try:
                logger.info(f"Searching archive with query: {archive_query}")
                search_results = await self._search_archive(jwt_token, archive_query)

                if search_results:
                    background_assets = self._handle_asset_selection(search_results)
                    if background_assets:
                        logger.info(f"User selected {len(background_assets)} background sources")
                    else:
                        logger.info("No background sources selected")
                else:
                    logger.info("No archive results found")

            except Exception as e:
                logger.error(f"Archive search failed: {str(e)}")
                # Continue without background sources

        # Initialize state
        current_headline = None
        current_body = None
        current_bullets = None
        current_advisory = None
        current_story = None

        # Main workflow loop
        while True:
            # Generate if needed
            if current_story is None:
                try:
                    logger.info(
                        f"Generating story update (mode={update_mode}, "
                        f"{len(background_assets)} background sources)"
                    )

                    current_headline, current_body, current_bullets, current_advisory, current_story = \
                        await self._generate_updated_story(
                            existing_story,
                            new_content_sources,
                            update_mode,
                            background_assets,
                            llm
                        )

                    logger.info("Generation successful")

                except Exception as e:
                    logger.error(f"Generation failed: {str(e)}")
                    return self._error_response(f"Story update generation failed: {str(e)}")

            # REVIEW INTERRUPT
            logger.info("Requesting story review from user")

            review_raw = interrupt({
                "type": INTERRUPT_TYPE_REVIEW,
                "message": "Review the updated story and choose an action",
                "context": {
                    "content": current_story,
                    "advisory": current_advisory,
                    "existing_story_usn": usn,
                    "update_mode": update_mode,
                    "background_sources": [
                        a.model_dump(mode="json", exclude_none=True)
                        for a in background_assets
                    ]
                }
            })

            # Interpret the user's response
            review_feedback = await interpreter.interpret_review_response(
                review_raw,
                {
                    "story": current_story,
                    "headline": current_headline,
                    "body": current_body,
                    "bullets": current_bullets,
                    "advisory": current_advisory
                }
            )

            action = review_feedback.get("action")
            logger.info(f"User action: {action}")

            # Handle user actions
            if action == ACTION_APPROVE:
                logger.info("Story update approved by user")
                return ToolResult(
                    content=[{"type": "text", "text": current_story}],
                    isError=False
                )

            elif action == ACTION_REGENERATE:
                logger.info("User requested regeneration")
                # Clear state to force regeneration
                current_story = None
                current_headline = None
                current_body = None
                current_bullets = None
                current_advisory = None
                # Continue loop to regenerate

            elif action == ACTION_REFINE:
                logger.info("User requested refinement")
                instructions = review_feedback.get("instructions", "")

                if instructions:
                    try:
                        refined_story = await self._refine_story(
                            current_story,
                            instructions,
                            llm
                        )
                        current_story = refined_story
                        logger.info("Refinement successful")
                    except Exception as e:
                        logger.error(f"Refinement failed: {str(e)}")
                        # Keep current version, continue loop

            elif action == ACTION_CANCEL:
                logger.info("User cancelled the workflow")
                return self._error_response("Story update cancelled by user", is_error=False)

            else:
                # Unknown action - treat as refinement request
                logger.warning(f"Unknown action '{action}', treating as refinement")
                try:
                    refined_story = await self._refine_story(
                        current_story,
                        str(review_raw),
                        llm
                    )
                    current_story = refined_story
                except Exception as e:
                    logger.error(f"Refinement failed: {str(e)}")
