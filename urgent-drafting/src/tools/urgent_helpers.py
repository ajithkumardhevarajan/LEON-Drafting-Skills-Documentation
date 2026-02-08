"""Helper functions for urgent drafting"""

from datetime import datetime
from typing import List, Optional
from ..models import Asset, SelectableAsset


def extract_day_of_week_from_asset(asset: Asset) -> Optional[str]:
    """
    Extracts day of week from asset's modified_at timestamp.

    Args:
        asset: Asset with modified_at timestamp

    Returns:
        Day of week name (e.g., "Monday") or None if not available
    """
    if not asset.modified_at:
        return None

    try:
        # Parse ISO format: 2025-09-19T16:12:56.4943191Z
        date_obj = datetime.fromisoformat(asset.modified_at.replace("Z", "+00:00"))
        return date_obj.strftime("%A")
    except Exception:
        return None


def format_urgent_content(headline: str, body: str) -> str:
    """
    Formats urgent content with proper HTML structure.

    Args:
        headline: Urgent headline
        body: Urgent body text (may contain double newlines between sentences)

    Returns:
        Formatted HTML string with headline and body paragraphs
    """
    # Format body with paragraph tags - split on double newlines (blank lines between sentences)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    formatted_body = "".join(f"<p>{p}</p>" for p in paragraphs)

    return f'<h3>{headline}</h3><div id="body">{formatted_body}</div>'


def format_urgent_sources(
    urgent: str,
    urgent_assets: List[SelectableAsset]
) -> str:
    """
    Prepends source alerts to existing urgent content.

    Args:
        urgent: Existing urgent HTML content
        urgent_assets: List of source assets to include

    Returns:
        Urgent content with source alerts prepended at the top (if assets provided)
    """
    if not urgent_assets:
        return urgent

    # Filter only included assets for sources
    included_assets = [asset for asset in urgent_assets if asset.included]

    if not included_assets:
        return urgent

    sources_section = ""
    for i, asset in enumerate(included_assets, 1):
        sources_section += f"[{i}] {asset.headline}<br>"
    sources_div = f'<div id="sources">{sources_section}</div>'

    return f"{sources_div}{urgent}"


def format_news_flashes(urgent_assets: List[Asset]) -> str:
    """
    Formats news flash assets into a string for urgent generation.

    Args:
        urgent_assets: List of news flash assets

    Returns:
        Formatted string with numbered news flashes
    """
    if not urgent_assets:
        return "No news flashes available."

    formatted = f"**News Flashes ({len(urgent_assets)})**: \n\n"
    for i, asset in enumerate(urgent_assets, 1):
        formatted += f"{i}. {asset.headline}\n"
    formatted += "\n"
    return formatted


def normalize_urgent_assets(assets: list | None) -> list[SelectableAsset]:
    """
    Convert dict representations to SelectableAsset objects.

    Args:
        assets: List of asset dicts or None

    Returns:
        List of SelectableAsset objects
    """
    if not assets:
        return []

    return [SelectableAsset(**asset) if isinstance(asset, dict) else asset for asset in assets]
