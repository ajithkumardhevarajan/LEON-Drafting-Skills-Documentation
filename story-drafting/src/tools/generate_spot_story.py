"""
Generate Spot Story Tool

This tool generates new spot stories from provided content sources with optional
archive search for background context. Implements the full workflow with
human-in-the-loop review using the MCP HITL framework.
"""

from typing import Any, Dict, Optional, List
import logging
import re
from mcp_hitl import resumable, interrupt

from .base import BaseTool
from ..models import ToolResult, Asset
from ..services import get_llm_orchestrator, get_intent_interpreter
from .spot_story_actions import (
    generate_spot_story_content,
    handle_refinement,
    handle_asset_selection,
    refine_story_content,
    ACTION_APPROVE,
    ACTION_REGENERATE,
    ACTION_REFINE,
    ACTION_CANCEL,
    ACTION_CREATE_DRAFT,
    INTERRUPT_TYPE_REVIEW,
    INTERRUPT_TYPE_REQUEST_INFO,
    INTERRUPT_TYPE_REFINEMENT,
    SKIP_SENTINEL,
    CANCEL_REFINEMENT_SENTINEL,
)
from ..services.semantic_search import search_semantic

logger = logging.getLogger(__name__)


class GenerateSpotStoryTool(BaseTool):
    """
    Tool for generating new spot stories from provided content.

    This tool implements the full spot story generation workflow:
    1. Search for relevant background sources using semantic search
    2. Generate story body using Gemini 2.5 Pro
    3. Generate headline, bullets, references
    4. Present for review (interrupt)
    5. Handle user feedback (approve/refine/regenerate/cancel)
    """

    @property
    def name(self) -> str:
        return "generate_spot_story"

    @property
    def description(self) -> str:
        return (
            "Generate a complete Reuters spot story from a user's request. "
            "The tool interprets the user's natural language request to extract content, "
            "and searches for relevant background sources using semantic search. "
            "Interactive workflow with generation, review, and refinement."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "request": {
                "type": "string",
                "description": (
                    "The user's natural language request for generating a spot story. "
                    "Can include: story idea, press release content, facts to cover. "
                    "The tool will automatically search for relevant background sources. "
                    "Example: 'Write a spot story about Apple's $500B US investment and Ford's EV strategy'"
                ),
                "required": True
            }
        }

    @property
    def response_mode(self) -> str:
        return "direct"  # Return direct response without orchestrator interpretation

    @property
    def orchestration_hints(self) -> Dict[str, Any]:
        """
        Fast-path routing hints to bypass LLM tool selection.

        When user input matches these patterns, route directly to this tool
        without asking the LLM which tool to use - saves ~1-2s latency.
        """
        return {
            "enabled": True,
            "priority": 10,
            "query_patterns": [
                # Case-insensitive patterns for spot story generation
                r"(?:write|create|draft|generate)\s+(?:a\s+)?spot\s+story",
                r"(?:new|make)\s+(?:a\s+)?spot\s+story",
                r"spot\s+story\s+(?:about|on|for)",
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
            "description": "Handles spot story generation requests"
        }

    def _error_response(self, message: str, is_error: bool = True) -> ToolResult:
        """Create a consistent error/info response."""
        return ToolResult(
            content=[{"type": "text", "text": message}],
            isError=is_error
        )

    def _has_substantial_content(self, request: str) -> bool:
        """
        Quick heuristic check for substantial content beyond trigger phrases.

        Returns True if the request contains actual content to extract,
        False if it's just a bare trigger phrase like "Draft a spot story".

        This allows us to skip the LLM call entirely for empty requests.
        """
        # Remove common trigger phrases
        trigger_patterns = [
            r"(?:write|create|draft|generate)\s+(?:a\s+)?(?:new\s+)?spot\s+story",
            r"(?:make|new)\s+(?:a\s+)?spot\s+story",
            r"spot\s+story\s+(?:about|on|for)?",
        ]
        cleaned = request.lower()
        for pattern in trigger_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Strip whitespace and punctuation
        cleaned = cleaned.strip(" .!?,;:")

        # Consider substantial if:
        # - More than 20 characters remaining (likely has actual content)
        # - Contains any digits (likely data/figures/dates)
        return len(cleaned) > 20 or bool(re.search(r'\d', cleaned))

    # Delegate methods for @resumable decorator caching

    async def _search_semantic(self, query: str) -> List[Asset]:
        return await search_semantic(query)

    def _handle_asset_selection(self, assets: List[Asset]) -> List[Asset]:
        return handle_asset_selection(assets)

    async def _generate_story(
        self,
        new_content_sources: str,
        background_assets: List[Asset],
        llm
    ):
        return await generate_spot_story_content(
            new_content_sources, background_assets, llm
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
        Execute spot story generation workflow.

        1. Search for relevant background sources using semantic search
        2. Generate complete spot story
        3. Present for review (interrupt)
        4. Handle user feedback (approve/refine/regenerate/cancel)
        5. Loop back to review after any changes
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

        # Quick heuristic check: if request is just a trigger phrase, skip LLM entirely
        if not self._has_substantial_content(user_request):
            logger.info("Request is just a trigger phrase - skipping LLM, asking for info")
            has_sufficient_content = False
            new_content_sources = ""
            use_archive = False
            archive_query = ""
            story_topic = "spot story"
        else:
            # Full LLM interpretation for requests with actual content
            try:
                logger.info(f"Interpreting user request: {user_request[:100]}...")
                extracted = await interpreter.interpret_spot_story_request(user_request)

                new_content_sources = extracted.content_sources
                has_sufficient_content = extracted.has_sufficient_content
                use_archive = extracted.use_archive
                archive_query = extracted.archive_query or ""
                story_topic = extracted.story_topic

                logger.info(
                    f"Extracted parameters - topic: {story_topic}, "
                    f"has_sufficient_content: {has_sufficient_content}, "
                    f"use_archive: {use_archive}, "
                    f"archive_query: {archive_query}, "
                    f"content_length: {len(new_content_sources)}"
                )

            except Exception as e:
                logger.error(f"Failed to interpret request: {e}")
                return self._error_response(f"Failed to understand request: {str(e)}")

        if not jwt_token:
            return self._error_response("Authentication token is required")

        # Check if user provided sufficient content
        if not has_sufficient_content:
            logger.info("User request lacks sufficient content - prompting for more information")
            # Trigger interrupt to ask for more information
            additional_info = interrupt({
                "type": INTERRUPT_TYPE_REQUEST_INFO,
                "message": "I need more information to draft a spot story. Please provide details such as:\n"
                           "- The main topic or event you want to write about\n"
                           "- Key facts, quotes, or data points\n"
                           "- Any press releases or source material\n"
                           "- Companies, people, or organizations involved\n\n"
                           "Example: 'Disney appointed Bob Iger as CEO and Ford announced a $50B EV investment.'"
            })

            # Handle response - extract text from dict or string
            if isinstance(additional_info, dict):
                user_text = (additional_info.get("text") or "").strip()
            elif isinstance(additional_info, str):
                user_text = additional_info.strip()
            else:
                user_text = ""

            # Clear sentinel value used to bypass CopilotKit's truthy check
            if user_text == SKIP_SENTINEL:
                user_text = ""

            # User provided additional info - update content and continue (no recursive call)
            if user_text:
                logger.info("User provided additional information, interpreting content")
                # Combine original request with additional info
                combined_request = f"{user_request}\n\n{user_text}"

                # Now interpret the combined request with LLM to extract structured content
                try:
                    extracted = await interpreter.interpret_spot_story_request(combined_request)
                    new_content_sources = extracted.content_sources
                    has_sufficient_content = extracted.has_sufficient_content
                    use_archive = extracted.use_archive
                    archive_query = extracted.archive_query or ""
                    story_topic = extracted.story_topic

                    logger.info(
                        f"Extracted parameters - topic: {story_topic}, "
                        f"has_sufficient_content: {has_sufficient_content}, "
                        f"content_length: {len(new_content_sources)}"
                    )

                    # If still insufficient, we can't proceed
                    if not has_sufficient_content:
                        logger.info("Still insufficient content after user input")
                        return self._error_response(
                            "The information provided is still not sufficient to generate a story. "
                            "Please provide more details about the topic, key facts, or source material.",
                            is_error=False
                        )

                except Exception as e:
                    logger.error(f"Failed to interpret combined request: {e}")
                    return self._error_response(f"Failed to understand request: {str(e)}")
            else:
                logger.info("User did not provide additional information")
                return self._error_response(
                    "No additional information provided. Cannot proceed with story generation.",
                    is_error=False
                )

        # Initialize state
        background_assets: List[Asset] = []
        search_completed = False  # Defensive flag to prevent duplicate search on resume
        current_headline = None
        current_body = None
        current_bullets = None
        current_story = None

        # Track refinement instructions to preserve across regenerations
        refinement_history: List[str] = []
        base_story_before_refinements = None

        # Step 1: Semantic search for background sources
        # Only search if user provided substantial content (LLM-determined)
        # The search_completed flag prevents re-running search after @resumable resume
        if has_sufficient_content and not search_completed:
            try:
                # Use the extracted content for search, not the original user request
                # (which might just be "draft a spot story")
                search_query = new_content_sources if new_content_sources else user_request
                logger.info(f"Searching for background sources with semantic search: {search_query[:100]}...")
                search_results = await self._search_semantic(search_query)
                search_completed = True  # Mark search as complete to prevent re-run on resume

                if search_results:
                    # Present for user selection via interrupt
                    background_assets = self._handle_asset_selection(search_results)
                    if background_assets:
                        logger.info(f"User selected {len(background_assets)} background sources")
                    else:
                        logger.info("No background sources selected")
                else:
                    logger.info("No semantic search results found")

            except KeyboardInterrupt:
                # Let interrupt exceptions propagate to @resumable decorator
                raise
            except Exception as e:
                # Check if this is an interrupt exception (contains "Interrupt requested")
                if "Interrupt requested" in str(e):
                    # Re-raise interrupt exceptions so they're handled by @resumable
                    raise
                logger.error(f"Semantic search failed: {str(e)}")
                # Continue without background sources
        else:
            logger.info("Skipping semantic search - insufficient content provided")

        # Main workflow loop
        while True:
            # Generate if needed
            if current_story is None:
                try:
                    logger.info(f"Generating spot story with {len(background_assets)} background sources")

                    current_headline, current_body, current_bullets, current_story = \
                        await self._generate_story(
                            new_content_sources,
                            background_assets,
                            llm
                        )

                    logger.info("Generation successful")

                    # Store as base story before any refinements are applied
                    base_story_before_refinements = current_story

                    # If we have refinement history, re-apply all refinements to the newly generated story
                    if refinement_history:
                        logger.info(f"Re-applying {len(refinement_history)} refinement(s) to regenerated story")
                        for i, instruction in enumerate(refinement_history, 1):
                            logger.info(f"Applying refinement {i}/{len(refinement_history)}: {instruction[:100]}...")
                            try:
                                current_story = await self._refine_story(
                                    current_story,
                                    instruction,
                                    llm
                                )
                            except Exception as e:
                                logger.error(f"Failed to re-apply refinement {i}: {str(e)}")
                        logger.info("All refinements re-applied successfully")

                except Exception as e:
                    logger.error(f"Generation failed: {str(e)}")
                    return self._error_response(f"Story generation failed: {str(e)}")

            # REVIEW INTERRUPT - Core of the workflow
            logger.info("Requesting story review from user")

            review_raw = interrupt({
                "type": INTERRUPT_TYPE_REVIEW,
                "message": "Review the generated story and choose an action",
                "context": {
                    "content": current_story,
                    "headline": current_headline,
                    "body": current_body,
                    "bullets": current_bullets,
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
                    "bullets": current_bullets
                }
            )

            action = review_feedback.get("action")
            logger.info(f"User action: {action}")

            # Handle user actions
            if action == ACTION_APPROVE:
                logger.info("Story approved by user")
                return ToolResult(
                    content=[{"type": "text", "text": current_story}],
                    isError=False
                )

            elif action == ACTION_REGENERATE:
                if refinement_history:
                    logger.info(
                        f"User requested regeneration - will regenerate and re-apply "
                        f"{len(refinement_history)} refinement(s)"
                    )
                else:
                    logger.info("User requested regeneration")

                # Clear state to force regeneration
                # Note: refinement_history is preserved and will be re-applied
                current_story = None
                current_headline = None
                current_body = None
                current_bullets = None
                # Continue loop to regenerate (refinements will be re-applied automatically)

            elif action == ACTION_REFINE:
                logger.info("User requested refinement")
                instructions = review_feedback.get("instructions", "")

                # If no instructions provided, prompt for them
                if not instructions:
                    refinement_input = interrupt({
                        "type": INTERRUPT_TYPE_REFINEMENT,
                        "message": "What specific changes would you like to make to this story?",
                        "context": {
                            "content": current_story,
                            "headline": current_headline,
                            "body": current_body,
                            "bullets": current_bullets,
                        }
                    })

                    if str(refinement_input).strip() == CANCEL_REFINEMENT_SENTINEL:
                        logger.info("User cancelled refinement")
                        continue  # Loop back to review
                    instructions = str(refinement_input).strip()

                if instructions:
                    # Store the base story before first refinement
                    if not refinement_history and base_story_before_refinements is None:
                        base_story_before_refinements = current_story
                        logger.info("Stored base story before refinements")

                    try:
                        refined_story = await self._refine_story(
                            current_story,
                            instructions,
                            llm
                        )
                        current_story = refined_story

                        # Add to refinement history for re-application on regeneration
                        refinement_history.append(instructions)
                        logger.info(f"Refinement successful (total refinements: {len(refinement_history)})")
                    except Exception as e:
                        logger.error(f"Refinement failed: {str(e)}")
                        # Keep current version, continue loop

            elif action == ACTION_CANCEL:
                logger.info("User cancelled the workflow")
                return self._error_response("Spot story generation cancelled by user", is_error=False)

            elif action == ACTION_CREATE_DRAFT:
                logger.info("User created draft in new tab")
                return ToolResult(
                    content=[{"type": "text", "text": "Your draft has been created."}],
                    isError=False,
                )

            else:
                # Unknown action - treat as refinement request with raw response
                logger.warning(f"Unknown action '{action}', treating as refinement")

                # Store the base story before first refinement
                if not refinement_history and base_story_before_refinements is None:
                    base_story_before_refinements = current_story
                    logger.info("Stored base story before refinements")

                try:
                    refined_story = await self._refine_story(
                        current_story,
                        str(review_raw),
                        llm
                    )
                    current_story = refined_story

                    # Add to refinement history for re-application on regeneration
                    refinement_history.append(str(review_raw))
                    logger.info(f"Refinement successful (total refinements: {len(refinement_history)})")
                except Exception as e:
                    logger.error(f"Refinement failed: {str(e)}")
