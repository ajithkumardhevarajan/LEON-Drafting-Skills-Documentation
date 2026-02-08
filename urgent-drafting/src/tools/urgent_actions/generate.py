"""Urgent content generation logic"""

import logging
from typing import List, Tuple, Any

from ...models import SelectableAsset
from ...prompts.reuters_prompts import BODY_PROMPT, HEADLINE_PROMPT
from ..urgent_helpers import (
    extract_day_of_week_from_asset,
    format_urgent_content,
    format_news_flashes,
)
from .constants import MODEL_GPT4, TEMPERATURE

logger = logging.getLogger(__name__)


async def generate_urgent_content(
    assets: List[SelectableAsset],
    llm: Any
) -> Tuple[str, str, str]:
    """
    Generate urgent content (headline, body, and formatted HTML) from included assets.

    Args:
        assets: List of selectable assets (will filter for included ones)
        llm: LLM orchestrator instance

    Returns:
        Tuple of (headline, body, formatted_urgent_html)

    Raises:
        ValueError: If no assets are selected for generation
    """
    # Filter only included assets
    included = [a for a in assets if a.included]

    if not included:
        raise ValueError("No assets selected for generation")

    # Lead asset for day of week extraction
    lead_asset = included[0]
    day_of_week = extract_day_of_week_from_asset(lead_asset)

    logger.info(f"Generating urgent from {len(included)} assets")

    # Generate body with full Reuters prompt
    body_messages = [
        {"role": "system", "content": BODY_PROMPT},
        {"role": "user", "content": format_news_flashes(included)}
    ]

    body = await llm.invoke(body_messages, temperature=TEMPERATURE, model=MODEL_GPT4)

    # Replace day placeholder
    if day_of_week:
        body = body.replace("<DOW_placeholder>", day_of_week)

    # Generate headline from body
    headline_messages = [
        {"role": "system", "content": HEADLINE_PROMPT},
        {"role": "user", "content": body}
    ]

    headline = await llm.invoke(headline_messages, temperature=TEMPERATURE, model=MODEL_GPT4)

    # Format as HTML
    urgent = format_urgent_content(headline, body)

    return headline, body, urgent
