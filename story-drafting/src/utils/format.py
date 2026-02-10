"""Formatting utilities for spot story generation.
"""

import re
from typing import List, Optional


def extract_article_content(spot_story_output: str) -> str:
    """Extract and combine article content, removing planning sections."""

    # Extract the article content between <article> tags
    article_match = re.search(r"<article>(.*?)</article>", spot_story_output, re.DOTALL)
    if not article_match:
        # If no article tags, use the whole output but try to remove planning
        content = spot_story_output
        # Remove article_planning section if present
        planning_match = re.search(
            r"<article_planning>(.*?)</article_planning>", content, re.DOTALL
        )
        if planning_match:
            content = content.replace(planning_match.group(0), "")
        return content.strip()

    # Extract the article content
    article_content = article_match.group(1).strip()

    # Extract the various parts of the article
    lead_match = re.search(r"<lead>(.*?)</lead>", article_content, re.DOTALL)
    details_match = re.search(
        r"<details_par>(.*?)</details_par>", article_content, re.DOTALL
    )
    nut_graph_match = re.search(
        r"<nut_graph>(.*?)</nut_graph>", article_content, re.DOTALL
    )
    quotes_match = re.search(r"<quotes>(.*?)</quotes>", article_content, re.DOTALL)
    background_match = re.search(
        r"<background>(.*?)</background>", article_content, re.DOTALL
    )

    # Combine the parts into a coherent article (without tags)
    combined_article = ""

    # Add lead paragraph
    if lead_match:
        lead = lead_match.group(1).strip()
        combined_article += lead + "\n\n"

    # Add details paragraphs
    if details_match:
        details = details_match.group(1).strip()
        combined_article += details + "\n\n"

    # Add nut graph
    if nut_graph_match:
        nut_graph = nut_graph_match.group(1).strip()
        combined_article += nut_graph + "\n\n"

    # Add quotes
    if quotes_match:
        quotes = quotes_match.group(1).strip()
        combined_article += quotes + "\n\n"

    # Add background
    if background_match:
        background = background_match.group(1).strip()
        combined_article += background

    return combined_article.strip()


def format_story_draft(
    headline: str,
    body: str,
    bullets: str,
    references: str = "",
    source_headlines: Optional[List[str]] = None,
    advisory: str = ""
) -> str:
    """Format the final output using HTML for better display consistency with linked references."""

    # Parse bullet points
    bullet_points = parse_bullets_output(bullets) if bullets else []

    # Build output using HTML
    html_sections = []

    # Add top anchor
    html_sections.append('<a id="top0"></a>')

    # Add headline
    if headline:
        html_sections.append(f"<h2><strong>{headline.strip()}</strong></h2>")

    # Add bullet points section
    if bullet_points:
        html_sections.append("<h3>Bullet Point Summary</h3>")
        html_sections.append("<ul>")
        for bullet in bullet_points:
            html_sections.append(f"<li>{bullet}</li>")
        html_sections.append("</ul>")

    # Add story section with references
    if body:
        html_sections.append("<h3>Story</h3>")

        # Use references if provided, otherwise use body
        story_text = references.strip() if references else body.strip()

        # Extract content from <content_with_references> tags if present
        content_match = re.search(
            r"<content_with_references>(.*?)</content_with_references>",
            story_text,
            re.DOTALL,
        )
        if content_match:
            story_text = content_match.group(1).strip()

        # Clean up any residual XML tags (except anchor tags)
        story_text = re.sub(r"<(?!/?a\b)[^>]+>", "", story_text)

        # Replace reference numbers with linked versions
        if source_headlines:
            for i in range(len(source_headlines)):
                ref_num = i + 1
                # Replace [ref_num] with linked version (avoiding already-linked ones)
                story_text = re.sub(
                    rf"(?<!>)\[{ref_num}\](?!</a>)",
                    f'<a id="top{ref_num}" href="#footnote{ref_num}">[{ref_num}]</a>',
                    story_text,
                )

        # Convert paragraphs to HTML
        paragraphs = story_text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if para:
                html_sections.append(f"<p>{para}</p>")

    # Add advisory section
    if advisory:
        html_sections.append("<h3>Advisory</h3>")
        html_sections.append(f"<p><em>{advisory.strip()}</em></p>")

    # Add numbered inputs with return links
    if source_headlines:
        html_sections.append("<h3>References</h3>")
        for i, headline_text in enumerate(source_headlines, start=1):
            html_sections.append(
                f'<p><a id="footnote{i}" href="#top0">[{i}]</a> <strong>{headline_text}</strong></p>'
            )

    return "\n".join(html_sections)


def parse_bullets_output(bullets_raw: str) -> List[str]:
    """Parse bullet points from the output and extract clean bullet list."""
    # Extract content between <bullet_points> tags
    bullet_match = re.search(
        r"<bullet_points>(.*?)</bullet_points>", bullets_raw, re.DOTALL
    )
    if bullet_match:
        bullets_content = bullet_match.group(1).strip()
    else:
        bullets_content = bullets_raw

    # Extract individual bullet points
    bullet_lines = []
    for line in bullets_content.split("\n"):
        line = line.strip()
        if line.startswith("•") or line.startswith("-") or line.startswith("*"):
            # Remove bullet marker and clean up
            clean_bullet = line[1:].strip()
            if clean_bullet:
                bullet_lines.append(clean_bullet)

    return bullet_lines
