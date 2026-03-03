"""Urgent content refinement logic"""

import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from mcp_hitl import interrupt

from ...models import SelectableAsset
from ...prompts.reuters_prompts import REFINEMENT_PROMPT
from ..urgent_helpers import format_urgent_content, format_news_flashes
from .constants import MODEL_GPT4, TEMPERATURE, INTERRUPT_TYPE_REFINEMENT

logger = logging.getLogger(__name__)


async def refine_urgent_content(
    headline: str,
    body: str,
    instructions: str,
    assets: List[SelectableAsset],
    llm: Any
) -> Tuple[str, str, str]:
    """
    Refine urgent content based on user instructions.

    Args:
        headline: Current headline
        body: Current body
        instructions: User's refinement instructions
        assets: List of selectable assets
        llm: LLM orchestrator instance

    Returns:
        Tuple of (refined_headline, refined_body, formatted_urgent_html)

    Raises:
        ValueError: If refinement fails or LLM returns an error
        json.JSONDecodeError: If LLM response cannot be parsed
    """
    included = [a for a in assets if a.included]

    refinement_messages = [
        {"role": "system", "content": REFINEMENT_PROMPT},
        {"role": "user", "content": f"""
            NEWS FLASHES: {format_news_flashes(included)}

            Current headline: {headline}
            Current body: {body}

            User feedback: {instructions}

            Return JSON with "headline" and "body" fields, or "error" if unable to refine.
        """}
    ]

    response = await llm.invoke(refinement_messages, temperature=TEMPERATURE, model=MODEL_GPT4)

    try:
        refined = json.loads(response)

        if refined.get("error"):
            raise ValueError(refined["error"])

        refined_headline = refined.get("headline", headline)
        refined_body = refined.get("body", body)

        # Format as HTML
        urgent = format_urgent_content(refined_headline, refined_body)

        return refined_headline, refined_body, urgent

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse refinement response: {str(e)}")
        raise ValueError(f"Refinement failed: could not parse LLM response")


async def handle_refinement(
    feedback: Dict[str, Any],
    current_headline: str,
    current_body: str,
    selectable_assets: List[SelectableAsset],
    llm: Any
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Process refinement request and return updated content.

    This function handles the full refinement flow including:
    - Extracting refinement instructions from feedback
    - Requesting instructions from user if not provided
    - Calling refine_urgent_content to perform the refinement
    - Handling errors gracefully

    Args:
        feedback: User feedback containing refinement instructions
        current_headline: Current urgent headline
        current_body: Current urgent body
        selectable_assets: Current asset selection
        llm: LLM orchestrator instance

    Returns:
        Tuple of (headline, body, urgent) or (None, None, None) if refinement fails
    """
    instructions = feedback.get("instructions", "")

    if not instructions:
        # Need specific instructions - interrupt for them
        logger.info("No instructions provided, requesting from user")

        refine_raw = interrupt({
            "type": INTERRUPT_TYPE_REFINEMENT,
            "message": "Could you provide specific feedback or changes you'd like to see in the urgent draft? This will help me refine it to better meet your needs.",
            "current_headline": current_headline,
            "current_body": current_body
        })

        # Simple extraction - could use interpreter for more sophistication
        instructions = str(refine_raw)

    if instructions:
        logger.info(f"Refining with instructions: {instructions[:100]}...")

        try:
            # Refine the urgent
            headline, body, urgent = await refine_urgent_content(
                current_headline,
                current_body,
                instructions,
                selectable_assets,
                llm
            )
            logger.info("Refinement successful")
            return headline, body, urgent

        except Exception as e:
            logger.error(f"Refinement failed: {str(e)}")
            # Return None to keep current version
            return None, None, None

    return None, None, None
