"""Spot story content generation logic

Ported from LangGraph implementation:
/reuters-assistant-langraph-api/src/projects/leon/graphs/spot_story_agent.py
"""

import logging
from typing import List, Tuple, Any, Optional

from ...models import Asset, SelectableAsset
from ...prompts.spot_story_prompts import (
    BODY_PROMPT,
    HEADLINE_PROMPT,
    BULLET_POINTS_PROMPT,
    REFERENCES_PROMPT,
)
from ...utils.format import extract_article_content, format_story_draft
from .constants import MODEL_GEMINI_2_5_PRO, TEMPERATURE

logger = logging.getLogger(__name__)


async def generate_body(
    new_content_sources: str,
    background_sources: Optional[str],
    llm: Any
) -> str:
    """
    Generate the main story body using Gemini 2.5 Pro.

    Args:
        new_content_sources: The user's story idea, press release, or fresh content
        background_sources: Formatted background sources from archive (optional)
        llm: LLM orchestrator instance

    Returns:
        Generated story body text
    """
    human_content = f"""
Here are the sources you will use to write the spot story.

New Content Sources:
{new_content_sources}

Background Sources:
{background_sources or "None provided"}
"""

    messages = [
        {"role": "system", "content": BODY_PROMPT},
        {"role": "user", "content": human_content}
    ]

    response = await llm.invoke(
        messages,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE
    )

    return extract_article_content(response)


async def generate_headline(body: str, llm: Any) -> str:
    """
    Generate a headline from the story body.

    Args:
        body: The generated story body
        llm: LLM orchestrator instance

    Returns:
        Generated headline text
    """
    messages = [
        {"role": "system", "content": HEADLINE_PROMPT},
        {"role": "user", "content": f"Here is the top of the story:\n{body}"}
    ]

    response = await llm.invoke(
        messages,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE
    )

    return response.strip()


async def generate_bullet_points(headline: str, body: str, llm: Any) -> str:
    """
    Generate 3 bullet point summaries.

    Args:
        headline: The generated headline
        body: The generated story body
        llm: LLM orchestrator instance

    Returns:
        Formatted bullet points
    """
    messages = [
        {"role": "system", "content": BULLET_POINTS_PROMPT},
        {"role": "user", "content": f"Headline: {headline}\n\nStory: {body}"}
    ]

    response = await llm.invoke(
        messages,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE
    )

    return response.strip()


async def generate_references(
    body: str,
    background_assets: List[Asset],
    llm: Any
) -> str:
    """
    Generate reference annotations linking paragraphs to sources.

    Args:
        body: The generated story body
        background_assets: List of background source assets
        llm: LLM orchestrator instance

    Returns:
        Story body with reference annotations
    """
    if not background_assets:
        return body

    # Build the inputs section from background_sources
    inputs_section = ""
    for i, asset in enumerate(background_assets, 1):
        inputs_section += f"<input_id>[{i}]</input_id> <input_content>{asset.headline}</input_content>\n"

    human_content = f"""
Here is the content you need to analyze:

<content>
{body}
</content>

Here are the numbered inputs used to write the content:

<inputs>
{inputs_section}
</inputs>

Instructions:
1. Carefully read through the content and the numbered inputs.
2. For each paragraph in the content, determine which input(s), if any, were used to write it.
3. Add reference numbers in square brackets at the end of each paragraph that has a corresponding input_id. For example: [1] or [1], [2]. Only focus on references within <input_id> tags. Ignore paragraph numbers that are not contained within <input_id> tags.
4. If a paragraph doesn't clearly correspond to any input_id, don't add any reference.
5. Maintain the original text of the content exactly, only adding references where appropriate.

Follow these steps:

1. List out each paragraph of the content, numbering them for easy reference.
2. For each paragraph, write down key phrases or ideas that might match the inputs.
3. Compare these key phrases to each input, noting any similarities or matches.
4. Make a decision on which input(s), if any, correspond to each paragraph.

This will help ensure a thorough interpretation of the data.

Output Format:
Provide the entire content with references added. Each paragraph should be on a new line, with references (if any) immediately following the paragraph text.

Example output structure:

<content_with_references>
First paragraph of the content. [2], [4]

Second paragraph of the content.

Third paragraph of the content. [1]
</content_with_references>

Please proceed with your analysis and reference-adding for the provided content. Answer in the format specified above.
"""

    messages = [
        {"role": "system", "content": REFERENCES_PROMPT},
        {"role": "user", "content": human_content}
    ]

    response = await llm.invoke(
        messages,
        model=MODEL_GEMINI_2_5_PRO,
        temperature=TEMPERATURE
    )

    return response.strip()


async def generate_spot_story_content(
    new_content_sources: str,
    background_assets: List[Asset],
    llm: Any
) -> Tuple[str, str, str, str]:
    """
    Generate complete spot story content (headline, body, bullets, formatted output).

    Args:
        new_content_sources: The user's story idea, press release, or fresh content
        background_assets: List of background source assets from archive
        llm: LLM orchestrator instance

    Returns:
        Tuple of (headline, body, bullets, formatted_story_html)
    """
    # Format background sources
    background_sources = None
    if background_assets:
        background_sources = "Background Sources:\n\n"
        for i, asset in enumerate(background_assets, 1):
            background_sources += f"Article {i}\n"
            background_sources += f"Headline: {asset.headline}\n"
            background_sources += f"Body: {asset.body}\n"
            if i < len(background_assets):
                background_sources += "\n---\n\n"

    logger.info(f"Generating spot story body with {len(background_assets)} background sources")

    # Generate body
    story_body = await generate_body(new_content_sources, background_sources, llm)

    # Generate references if there are background assets
    story_body_with_references = ""
    source_headlines = None
    if background_assets:
        story_body_with_references = await generate_references(story_body, background_assets, llm)
        source_headlines = [asset.headline for asset in background_assets]

    # Generate headline
    story_headline = await generate_headline(story_body, llm)

    # Generate bullet points
    story_bullets = await generate_bullet_points(story_headline, story_body, llm)

    # Format as HTML
    formatted_story = format_story_draft(
        story_headline,
        story_body,
        story_bullets,
        story_body_with_references,
        source_headlines,
    )

    logger.info("Spot story generation complete")

    return story_headline, story_body, story_bullets, formatted_story


def format_background_sources_for_display(assets: List[Asset]) -> str:
    """
    Format background sources for display in the review UI.

    Args:
        assets: List of background source assets

    Returns:
        Formatted HTML string for display
    """
    if not assets:
        return ""

    html_parts = ["<h3>Background Sources</h3>", "<ul>"]
    for asset in assets:
        html_parts.append(f"<li><strong>{asset.headline}</strong></li>")
    html_parts.append("</ul>")

    return "\n".join(html_parts)
