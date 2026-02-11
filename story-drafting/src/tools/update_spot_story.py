"""
Update Spot Story Tool

This tool updates existing spot stories by integrating new information.
Supports two modes: add_background (preserve lede) and story_rewrite (new lede).
Implements the full workflow with human-in-the-loop review.
"""

from typing import Any, Dict, Optional, List
import logging
import re
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
    INTERRUPT_TYPE_REQUEST_INFO,
    SKIP_SENTINEL,
    UpdateMode,
)
from ..services.semantic_search import search_semantic

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
            "IMPORTANT: When Page Context is available in the system message, you MUST extract and pass: "
            "(1) usn from '**USN:**' field, (2) page_story_title from '**Headline:**' field, "
            "(3) page_story_summary from '**Body:**' field. "
            "Supports 'add_background' (preserve lede) or 'story_rewrite' (new lede) modes. "
            "Uses semantic search to find related background sources. "
            "Interactive workflow with generation, review, and refinement."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "request": {
                "type": "string",
                "description": (
                    "The user's full natural language request for updating a spot story. "
                    "Pass the complete user query here. "
                    "Example: 'Update story LXN3VG03Q with new info that the deal closes in Q1'"
                ),
                "required": False
            },
            "usn": {
                "type": "string",
                "description": (
                    "The USN (Unique Story Number) of the story to update. "
                    "Format: alphanumeric, 6-12 characters (e.g., 'LXN3VG03Q'). "
                    "IMPORTANT: Extract this from the Page Context if available (look for '**USN:**' field). "
                    "Optional if story content is provided via page_story_title/page_story_summary."
                ),
                "required": False
            },
            "mode": {
                "type": "string",
                "description": (
                    "The update mode: 'story_rewrite' (create new lede from new info) or "
                    "'add_background' (preserve existing lede, add new info as background)"
                ),
                "enum": ["story_rewrite", "add_background"],
                "required": False
            },
            "new_content": {
                "type": "string",
                "description": (
                    "The new information, instructions, or content to incorporate into the story. "
                    "This could be new facts, style instructions, or refinement requests. "
                    "Example: 'The deal closes in Q1' or 'Make it more professional'"
                ),
                "required": False
            },
            "page_story_title": {
                "type": "string",
                "description": (
                    "REQUIRED when Page Context is available: Extract the headline from '**Headline:**' field in the Page Context. "
                    "This is the current story's headline that the user wants to update."
                ),
                "required": False
            },
            "page_story_summary": {
                "type": "string",
                "description": (
                    "REQUIRED when Page Context is available: Extract the body content from '**Body:**' field in the Page Context. "
                    "This is the current story's body text that the user wants to update."
                ),
                "required": False
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

        Parameter extractions use JSONPath to pull data from external_context JSON:
        - $.story.usn -> usn parameter
        - $.story.headline -> page_story_title parameter
        - $.story.body -> page_story_summary parameter
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
                # New patterns for page context flow (no USN required)
                r"(?:draft|write|create)\s+(?:an?\s+)?update",
                r"update\s+(?:this\s+)?story",
                r"(?:draft|write)\s+(?:a\s+)?(?:story\s+)?update",
            ],
            "parameter_extractions": [
                {
                    "parameter_name": "request",
                    "jsonpath": None,
                    "fallback": "user_query",
                    "required": True,
                    "default": None
                },
                {
                    "parameter_name": "usn",
                    "jsonpath": "$.story.usn",
                    "fallback": None,
                    "required": False,
                    "default": None
                },
                {
                    "parameter_name": "page_story_title",
                    "jsonpath": "$.story.headline",
                    "fallback": None,
                    "required": False,
                    "default": None
                },
                {
                    "parameter_name": "page_story_summary",
                    "jsonpath": "$.story.body",
                    "fallback": None,
                    "required": False,
                    "default": None
                }
            ],
            "description": "Handles spot story update requests with USN or page context"
        }

    def _error_response(self, message: str, is_error: bool = True) -> ToolResult:
        """Create a consistent error/info response."""
        return ToolResult(
            content=[{"type": "text", "text": message}],
            isError=is_error
        )

    def _extract_usn_from_text(self, text: str) -> Optional[str]:
        """
        Extract USN from user query text.

        USN format: alphanumeric, 6-12 characters (e.g., 'LXN3VG03Q', 'LUN3XF21W').
        Looks for patterns like:
        - "USN LUN3XF21W"
        - "story LUN3XF21W"
        - "for LUN3XF21W"

        Args:
            text: The user's request text

        Returns:
            Extracted USN string or None if not found
        """
        if not text:
            return None

        # Pattern to match USN - alphanumeric 6-12 chars, typically starts with L
        # Look for USN preceded by common keywords
        patterns = [
            r'\bUSN\s+([A-Z0-9]{6,12})\b',           # "USN LUN3XF21W"
            r'\bstory\s+([A-Z0-9]{6,12})\b',         # "story LUN3XF21W"
            r'\bfor\s+([A-Z0-9]{6,12})\b',           # "for LUN3XF21W"
            r'\bupdate\s+([A-Z0-9]{6,12})\b',        # "update LUN3XF21W"
            r'\b(L[A-Z0-9]{5,11})\b',                # Standalone USN starting with L
        ]

        text_upper = text.upper()

        for pattern in patterns:
            match = re.search(pattern, text_upper, re.IGNORECASE)
            if match:
                usn = match.group(1)
                logger.info(f"Extracted USN from query: {usn}")
                return usn

        return None

    # Delegate methods for @resumable decorator caching

    async def _fetch_story(self, jwt_token: str, usn: str) -> Optional[Asset]:
        return await fetch_existing_story(jwt_token, usn)

    def _select_update_mode(self) -> UpdateMode:
        return select_update_mode()

    async def _search_archive(self, jwt_token: str, query: str) -> List[Asset]:
        return await search_archive_assets(jwt_token, query)

    async def _search_semantic(self, query: str) -> List[Asset]:
        """Delegate for semantic search to support @resumable caching."""
        return await search_semantic(query)

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

        1. Determine story source (USN fetch or page context)
        2. Request additional info if needed (request_info interrupt)
        3. Prompt for update mode selection
        4. Semantic search for background sources
        5. Generate updated story
        6. Present for review (interrupt)
        7. Handle user feedback (approve/refine/regenerate/cancel)
        """
        # Initialize services
        llm = get_llm_orchestrator()
        interpreter = get_intent_interpreter()

        # Debug: log received arguments
        logger.info(f"Received arguments: {arguments}")
        logger.info(f"Arguments keys: {list(arguments.keys())}")

        # Extract page context parameters (from fast-path JSONPath extraction)
        page_story_title = arguments.get("page_story_title")
        page_story_summary = arguments.get("page_story_summary")

        # Check for direct USN parameter
        direct_usn = arguments.get("usn")

        # Check for USN in the user's request text (highest priority)
        request_text = arguments.get("request", "")
        usn_from_query = self._extract_usn_from_text(request_text)

        # Initialize variables
        usn = None
        existing_story = None
        new_content_sources = ""
        has_sufficient_content = True
        update_mode_preset = None
        use_archive = False
        archive_query = ""

        # PRIORITY: USN in query > Page context > USN parameter > Natural language
        # If USN is found in the user's query, fetch that story (overrides page context)
        if usn_from_query:
            logger.info(f"USN found in query: {usn_from_query} - will fetch story (overrides page context)")
            usn = usn_from_query
            # Extract any additional content from the request (after removing USN patterns)
            new_content_sources = (
                arguments.get("new_content") or
                arguments.get("content") or
                arguments.get("new_information") or
                arguments.get("instructions") or
                ""
            )
            # Check if request has specific update content beyond just "draft an update for USN X"
            generic_patterns = [
                "draft an update", "draft update", "write an update", "write update",
                "create an update", "create update", "update story", "update this story",
                "for usn", "for story"
            ]
            is_generic_request = any(
                pattern in request_text.lower() for pattern in generic_patterns
            )
            # If only generic request with USN, we need more info
            if not new_content_sources.strip():
                has_sufficient_content = False
            else:
                has_sufficient_content = True

            logger.info(
                f"USN from query flow - usn: {usn}, has_sufficient_content: {has_sufficient_content}, "
                f"is_generic_request: {is_generic_request}"
            )

        # If no USN in query, check for page context
        elif page_story_title and page_story_summary:
            # Story content from page context - create Asset directly
            logger.info(f"Using page context - title: {page_story_title[:50]}...")
            existing_story = Asset(
                id="page_context",
                headline=page_story_title,
                body=page_story_summary,
                usn=direct_usn  # Include USN if available (for reference)
            )
            # Extract new content from request - check multiple possible fields
            new_content_sources = (
                arguments.get("new_content") or
                arguments.get("content") or
                arguments.get("new_information") or
                arguments.get("instructions") or
                ""
            )
            # Check if user provided specific update content or just a generic request
            request_text = arguments.get("request", "")
            generic_patterns = [
                "draft an update", "draft update", "write an update", "write update",
                "create an update", "create update", "update story", "update this story"
            ]
            is_generic_request = any(
                pattern in request_text.lower() for pattern in generic_patterns
            )
            # Only consider content sufficient if it's not just echoing the generic request
            if new_content_sources.strip() and new_content_sources.strip().lower() not in generic_patterns:
                has_sufficient_content = True
            else:
                has_sufficient_content = False

            logger.info(
                f"Page context flow - has_sufficient_content: {has_sufficient_content}, "
                f"is_generic_request: {is_generic_request}"
            )

        elif direct_usn:
            # No page context but have USN - will need to fetch story
            logger.info(f"Using USN parameter (no page context) - usn: {direct_usn}")
            usn = direct_usn
            # Check multiple possible field names for the new content/instructions
            new_content_sources = (
                arguments.get("new_content") or
                arguments.get("content") or
                arguments.get("new_information") or
                arguments.get("instructions") or
                arguments.get("request") or
                arguments.get("query") or
                arguments.get("message") or
                ""
            )

            # Map mode string to UpdateMode literal values
            direct_mode = arguments.get("mode")
            if direct_mode == "story_rewrite":
                update_mode_preset = "story_rewrite"
            elif direct_mode == "add_background":
                update_mode_preset = "add_background"

            use_archive = arguments.get("use_archive", False)
            archive_query = arguments.get("archive_query", "")

            logger.info(
                f"Direct USN params - usn: {usn}, mode: {direct_mode}, "
                f"content_length: {len(new_content_sources)}"
            )

        else:
            # Fall back to extracting from natural language request
            user_request = (
                arguments.get("request") or
                arguments.get("user_request") or
                arguments.get("message") or
                arguments.get("query") or
                arguments.get("input") or
                ""
            )

            if not user_request:
                return self._error_response(
                    "Could not find story to update. Please either:\n"
                    "- Provide a USN (e.g., 'Update story LXN3VG03Q with...')\n"
                    "- Open a story in LEON so I can use the page context"
                )

            # Use intent interpreter to extract structured parameters
            try:
                logger.info(f"Interpreting user request: {user_request[:100]}...")
                extracted = await interpreter.interpret_story_update_request(user_request)

                usn = extracted.usn
                new_content_sources = extracted.new_content
                has_sufficient_content = extracted.has_sufficient_content
                use_archive = extracted.use_archive
                archive_query = extracted.archive_query or ""

                logger.info(
                    f"Extracted parameters - usn: {usn}, "
                    f"has_sufficient_content: {has_sufficient_content}, "
                    f"use_archive: {use_archive}, "
                    f"content_length: {len(new_content_sources)}"
                )

            except Exception as e:
                logger.error(f"Failed to interpret request: {e}")
                return self._error_response(f"Failed to understand request: {str(e)}")

            # Check if we have a story source
            if not usn and not (page_story_title and page_story_summary):
                return self._error_response(
                    "Could not find story to update. Please either:\n"
                    "- Provide a USN (e.g., 'Update story LXN3VG03Q with...')\n"
                    "- Open a story in LEON so I can use the page context"
                )

        if not jwt_token:
            return self._error_response("Authentication token is required")

        # Step 1: Determine story source and fetch if needed
        if existing_story is None and usn:
            logger.info(f"Fetching existing story with USN: {usn}")
            try:
                existing_story = await self._fetch_story(jwt_token, usn)
                if not existing_story:
                    return self._error_response(f"No story found with USN: {usn}")
                logger.info(f"Found story: {existing_story.headline[:50]}...")
            except Exception as e:
                logger.error(f"Failed to fetch story: {str(e)}")
                return self._error_response(f"Failed to fetch story: {str(e)}")

        if existing_story is None:
            return self._error_response(
                "Could not find story to update. Please either:\n"
                "- Provide a USN (e.g., 'Update story LXN3VG03Q with...')\n"
                "- Open a story in LEON so I can use the page context"
            )

        # Step 2: Request additional info if needed
        if not has_sufficient_content or not new_content_sources.strip():
            logger.info("Insufficient content - prompting for more information")
            additional_info = interrupt({
                "type": INTERRUPT_TYPE_REQUEST_INFO,
                "message": (
                    f"I found the story: **{existing_story.headline}**\n\n"
                    "What information would you like to include in this update? Please provide:\n"
                    "- New facts, figures, or data points\n"
                    "- New quotes or statements\n"
                    "- New developments or events\n"
                    "- Any context or background to add\n\n"
                    "Example: 'The deal is now expected to close in Q1 2025, "
                    "and the company announced additional cost savings of $500M.'"
                )
            })

            # User provided additional info - handle string responses
            # Dict format for backward compatibility, but we only use the text
            if isinstance(additional_info, dict):
                user_text = (additional_info.get("text") or "").strip()
            elif isinstance(additional_info, str):
                user_text = additional_info.strip()
            else:
                user_text = ""

            # Clear sentinel value used to bypass CopilotKit's truthy check
            if user_text == SKIP_SENTINEL:
                user_text = ""

            # Add user text to content sources if provided
            if user_text:
                logger.info("User provided additional information for update")
                if new_content_sources.strip():
                    new_content_sources = f"{new_content_sources}\n\n{user_text}"
                else:
                    new_content_sources = user_text
            else:
                # User skipped - proceed to source selection
                # Selected sources will provide context for the update
                logger.info("User skipped additional info prompt, proceeding to source selection")

        # Step 3: Semantic search for background sources
        background_assets: List[Asset] = []

        # Build semantic search query from story headline, full body, and new content
        story_body = existing_story.body or ""
        search_query = f"{existing_story.headline} {story_body} {new_content_sources}"
        try:
            logger.info(f"Searching for background sources with semantic search")
            search_results = await self._search_semantic(search_query)

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
            # Check if this is an interrupt exception
            if "Interrupt requested" in str(e):
                raise
            logger.error(f"Semantic search failed: {str(e)}")
            # Continue without background sources

        # Step 4: Archive search if explicitly requested (in addition to semantic)
        if use_archive and archive_query:
            try:
                logger.info(f"Searching archive with query: {archive_query}")
                archive_results = await self._search_archive(jwt_token, archive_query)

                if archive_results:
                    # Filter out duplicates (assets already in background_assets)
                    existing_ids = {a.id for a in background_assets}
                    new_archive_assets = [a for a in archive_results if a.id not in existing_ids]

                    if new_archive_assets:
                        additional_assets = self._handle_asset_selection(new_archive_assets)
                        if additional_assets:
                            background_assets.extend(additional_assets)
                            logger.info(f"Added {len(additional_assets)} archive sources")
                else:
                    logger.info("No archive results found")

            except Exception as e:
                logger.error(f"Archive search failed: {str(e)}")
                # Continue without additional archive sources

        # Step 5: Select update mode (use preset if provided, otherwise prompt)
        if update_mode_preset:
            update_mode = update_mode_preset
            logger.info(f"Using preset update mode: {update_mode}")
        else:
            logger.info("Requesting update mode selection from user")
            update_mode = self._select_update_mode()
            logger.info(f"Selected update mode: {update_mode}")

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
