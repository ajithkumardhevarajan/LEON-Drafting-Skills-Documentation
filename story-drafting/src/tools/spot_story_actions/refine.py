"""Spot story content refinement logic
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from mcp_hitl import interrupt

from ...models import Asset
from ...prompts.spot_story_prompts import REFINEMENT_PROMPT
from ...utils.format import format_story_draft
from .constants import MODEL_GEMINI_2_5_PRO, TEMPERATURE, GEMINI_EXTRA_BODY, INTERRUPT_TYPE_REFINEMENT

logger = logging.getLogger(__name__)


async def refine_story_content(
    story_draft: str,
    requested_change: str,
    llm: Any
) -> str:
    """
    Make surgical changes to existing story based on user request.

    Args:
        story_draft: Current story draft (full HTML content)
        requested_change: Specific change requested by user
        llm: LLM orchestrator instance

    Returns:
        Refined story content
    """
    human_content = f"""
Current story draft:
{story_draft}

User requested change:
{requested_change}

Return the full updated story content, maintaining the same format as the input.
"""

    messages = [
        {"role": "system", "content": REFINEMENT_PROMPT},
        {"role": "user", "content": human_content}
    ]

    response = await llm.invoke(
        messages,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE,
        extra_body=GEMINI_EXTRA_BODY
    )

    return response.strip()


async def handle_refinement(
    feedback: Dict[str, Any],
    current_story_draft: str,
    current_headline: str,
    current_body: str,
    current_bullets: str,
    background_assets: List[Asset],
    llm: Any
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Process refinement request and return updated content.

    This function handles the full refinement flow including:
    - Extracting refinement instructions from feedback
    - Requesting instructions from user if not provided
    - Calling refine_story_content to perform the refinement
    - Handling errors gracefully

    Args:
        feedback: User feedback containing refinement instructions
        current_story_draft: Current formatted story draft
        current_headline: Current headline
        current_body: Current body
        current_bullets: Current bullets
        background_assets: Background source assets
        llm: LLM orchestrator instance

    Returns:
        Tuple of (headline, body, bullets, formatted_story) or (None, None, None, None) if refinement fails
    """
    instructions = feedback.get("instructions", "")

    if not instructions:
        # Need specific instructions - interrupt for them
        logger.info("No instructions provided, requesting from user")

        refine_raw = interrupt({
            "type": INTERRUPT_TYPE_REFINEMENT,
            "message": "What specific changes would you like?",
            "context": {
                "content": current_story_draft,
                "headline": current_headline,
                "body": current_body,
                "bullets": current_bullets,
            }
        })

        # Simple extraction
        instructions = str(refine_raw)

    if instructions:
        logger.info(f"Refining with instructions: {instructions[:100]}...")

        try:
            # Refine the story content
            refined_content = await refine_story_content(
                current_story_draft,
                instructions,
                llm
            )

            # For now, we return the refined content as-is
            # The formatted HTML includes headline, bullets, and body
            # In a more sophisticated implementation, we could parse these out

            logger.info("Refinement successful")
            return current_headline, current_body, current_bullets, refined_content

        except Exception as e:
            logger.error(f"Refinement failed: {str(e)}")
            # Return None to keep current version
            return None, None, None, None

    return None, None, None, None
