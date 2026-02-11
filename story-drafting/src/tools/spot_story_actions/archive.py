"""Archive search and asset selection for spot stories

Handles searching Reuters archive and user asset selection.
"""

import json
import logging
from typing import List, Optional
from mcp_hitl import interrupt

from ...models import Asset, SelectableAsset
from ...services.asset_api import search_archive_stories
from .constants import INTERRUPT_TYPE_ASSETS_SELECTION

logger = logging.getLogger(__name__)


async def search_archive_assets(
    auth_token: str,
    query: str,
    take: int = 30
) -> List[Asset]:
    """
    Search Reuters archive for background source articles.

    Args:
        auth_token: JWT token for authentication
        query: Search keywords
        take: Maximum number of results

    Returns:
        List of Asset objects from archive
    """
    logger.info(f"Searching archive with query: {query}")

    assets = await search_archive_stories(
        auth_token=auth_token,
        query=query,
        take=take
    )

    logger.info(f"Found {len(assets)} assets in archive")
    return assets


def handle_asset_selection(assets: List[Asset]) -> List[Asset]:
    """
    Present assets to user for selection and return selected assets.

    This function uses an interrupt to present the search results to the user
    and allows them to select which assets to include as background sources.

    Args:
        assets: List of assets from archive search

    Returns:
        List of selected Asset objects
    """
    if not assets:
        logger.info("No assets to select from")
        return []

    logger.info(f"Presenting {len(assets)} assets for selection")

    # Interrupt to get user's selection
    # Note: Backend expects "options" key for the selectable items
    selected_asset_ids_raw = interrupt({
        "type": INTERRUPT_TYPE_ASSETS_SELECTION,
        "message": "Select the articles you would like to use as background sources for your story.",
        "options": [
            asset.model_dump(mode="json", exclude_none=True)
            for asset in assets
        ]
    })

    # Parse the selection
    try:
        if isinstance(selected_asset_ids_raw, str):
            selected_asset_ids = json.loads(selected_asset_ids_raw)
        elif isinstance(selected_asset_ids_raw, list):
            selected_asset_ids = selected_asset_ids_raw
        else:
            selected_asset_ids = []
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse asset selection, using empty selection")
        selected_asset_ids = []

    if not selected_asset_ids:
        logger.info("No assets selected from archive search")
        return []

    # Filter to selected assets
    selected_assets = [
        asset for asset in assets
        if asset.id in selected_asset_ids
    ]

    logger.info(f"User selected {len(selected_assets)} assets")
    return selected_assets


def convert_to_selectable_assets(
    assets: List[Asset],
    included_by_default: bool = True
) -> List[SelectableAsset]:
    """
    Convert Asset objects to SelectableAsset objects.

    Args:
        assets: List of Asset objects
        included_by_default: Whether assets should be included by default

    Returns:
        List of SelectableAsset objects
    """
    return [
        SelectableAsset(
            id=asset.id,
            headline=asset.headline,
            body=asset.body,
            modified_at=asset.modified_at,
            usn=asset.usn,
            included=included_by_default
        )
        for asset in assets
    ]


def get_selected_headlines(assets: List[Asset]) -> List[str]:
    """
    Get list of headlines from selected assets.

    Args:
        assets: List of selected Asset objects

    Returns:
        List of headline strings
    """
    return [f'"{asset.headline}"' for asset in assets]
