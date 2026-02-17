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


def handle_asset_selection(assets: List[Asset]) -> tuple[List[Asset], bool]:
    """
    Present assets to user for selection and return selected assets and additional info flag.

    This function uses an interrupt to present the search results to the user
    and allows them to select which assets to include as background sources.
    User can choose to provide additional information before generation.

    Args:
        assets: List of assets from archive search

    Returns:
        Tuple of (List of selected Asset objects, bool indicating if user wants to provide additional info)
    """
    if not assets:
        logger.info("No assets to select from")
        return [], False

    logger.info(f"Presenting {len(assets)} assets for selection")

    # Interrupt to get user's selection
    # Note: Backend expects "options" key for the selectable items
    selection_response = interrupt({
        "type": INTERRUPT_TYPE_ASSETS_SELECTION,
        "message": "Select the articles you would like to use as background sources for your story.",
        "options": [
            asset.model_dump(mode="json", exclude_none=True)
            for asset in assets
        ]
    })

    # Parse the selection - handle new format with assets and provideAdditionalInfo flag
    provide_additional_info = False
    selected_asset_ids = []

    # Debug logging to understand response format
    logger.info(f"Asset selection response type: {type(selection_response)}")
    logger.info(f"Asset selection response: {str(selection_response)[:200]}")

    try:
        if isinstance(selection_response, str):
            selection_response = json.loads(selection_response)
            logger.info(f"Parsed JSON response type: {type(selection_response)}")

        # New format: {assets: [...], provideAdditionalInfo: bool}
        if isinstance(selection_response, dict) and 'assets' in selection_response:
            assets_data = selection_response.get('assets', [])
            provide_additional_info = selection_response.get('provideAdditionalInfo', False)

            if isinstance(assets_data, list):
                if len(assets_data) > 0 and isinstance(assets_data[0], dict):
                    # Extract IDs from objects
                    selected_asset_ids = [item.get('id') for item in assets_data if isinstance(item, dict) and 'id' in item]
                else:
                    # List of IDs
                    selected_asset_ids = assets_data
        # Fallback: old format (list of assets or IDs)
        elif isinstance(selection_response, list):
            if len(selection_response) > 0 and isinstance(selection_response[0], dict):
                # Old format: extract IDs from objects
                selected_asset_ids = [item.get('id') for item in selection_response if isinstance(item, dict) and 'id' in item]
            else:
                # Old format: list of IDs
                selected_asset_ids = selection_response
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse asset selection: {e}, using empty selection")
        selected_asset_ids = []

    if not selected_asset_ids:
        logger.info("No assets selected from archive search")
        return [], provide_additional_info

    # Filter to selected assets
    selected_assets = [
        asset for asset in assets
        if asset.id in selected_asset_ids
    ]

    logger.info(f"User selected {len(selected_assets)} assets, provide_additional_info={provide_additional_info}")
    return selected_assets, provide_additional_info


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
