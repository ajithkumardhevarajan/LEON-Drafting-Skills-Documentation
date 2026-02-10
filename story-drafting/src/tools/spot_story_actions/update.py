"""Story update generation logic
"""

import logging
from typing import List, Tuple, Any, Optional

from ...models import Asset
from ...prompts.spot_story_prompts import (
    STORY_UPDATE_BODY_PROMPT,
    HEADLINE_PROMPT,
    BULLET_POINTS_PROMPT,
)
from ...services.intent_models import StoryUpdateOutput
from ...utils.format import format_story_draft
from .constants import MODEL_GEMINI_2_5_PRO, TEMPERATURE
from .generate import generate_headline, generate_bullet_points, generate_references
from .update_mode import UpdateMode

logger = logging.getLogger(__name__)


async def generate_updated_story_body(
    existing_story: Asset,
    new_content_sources: str,
    update_mode: UpdateMode,
    background_sources: Optional[str],
    llm: Any
) -> StoryUpdateOutput:
    """
    Generate updated story body using structured output.

    Args:
        existing_story: The existing story being updated
        new_content_sources: New information to add
        update_mode: Either 'add_background' or 'story_rewrite'
        background_sources: Formatted background sources (optional)
        llm: LLM orchestrator instance

    Returns:
        StoryUpdateOutput with updated_story and advisory
    """
    existing_story_text = f"""
Headline:
{existing_story.headline}

Body:
{existing_story.body}
"""

    human_content = f"""
Update mode:
{update_mode}

Existing Story:
{existing_story_text}

New Content Sources:
{new_content_sources}

Background Sources:
{background_sources or "None provided"}
"""

    messages = [
        {"role": "system", "content": STORY_UPDATE_BODY_PROMPT},
        {"role": "user", "content": human_content}
    ]

    response = await llm.invoke_structured(
        messages,
        response_model=StoryUpdateOutput,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE
    )

    return response


async def generate_updated_spot_story_content(
    existing_story: Asset,
    new_content_sources: str,
    update_mode: UpdateMode,
    background_assets: List[Asset],
    llm: Any
) -> Tuple[str, str, str, str, str]:
    """
    Generate complete updated spot story content.

    Args:
        existing_story: The existing story being updated
        new_content_sources: New information to add
        update_mode: Either 'add_background' or 'story_rewrite'
        background_assets: List of background source assets from archive
        llm: LLM orchestrator instance

    Returns:
        Tuple of (headline, body, bullets, advisory, formatted_story_html)
    """
    # Format background sources
    background_sources = None
    if background_assets:
        background_sources = "Additional Background Sources:\n\n"
        for i, asset in enumerate(background_assets, 1):
            background_sources += f"Article {i}\n"
            background_sources += f"Headline: {asset.headline}\n"
            background_sources += f"Body: {asset.body}\n"
            if i < len(background_assets):
                background_sources += "\n---\n\n"

    logger.info(
        f"Generating story update with mode={update_mode}, "
        f"{len(background_assets)} background sources"
    )

    # Generate updated body with advisory
    update_output = await generate_updated_story_body(
        existing_story,
        new_content_sources,
        update_mode,
        background_sources,
        llm
    )

    story_body = update_output.updated_story
    advisory = update_output.advisory

    # Generate references if there are background assets
    story_body_with_references = ""
    source_headlines = None
    if background_assets:
        story_body_with_references = await generate_references(
            story_body, background_assets, llm
        )
        source_headlines = [asset.headline for asset in background_assets]

    # Generate headline
    story_headline = await generate_headline(story_body, llm)

    # Generate bullet points
    story_bullets = await generate_bullet_points(story_headline, story_body, llm)

    # Format as HTML with advisory
    formatted_story = format_story_draft(
        story_headline,
        story_body,
        story_bullets,
        story_body_with_references,
        source_headlines,
        advisory,
    )

    logger.info("Story update generation complete")

    return story_headline, story_body, story_bullets, advisory, formatted_story
