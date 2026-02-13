"""Asset management utilities for urgent drafting"""

import logging
from typing import List, Tuple, Optional

from ...models import SelectableAsset
from ...services.asset_api import search_assets

logger = logging.getLogger(__name__)


async def retrieve_and_prepare_assets(
    usn: str,
    jwt_token: str
) -> Tuple[List[SelectableAsset], List[SelectableAsset]]:
    """
    Retrieve assets from API and prepare both working and original lists.

    Args:
        usn: USN to search for
        jwt_token: JWT token for API authentication

    Returns:
        Tuple of (working_assets, original_assets) - both lists of SelectableAssets

    Raises:
        Exception: If asset retrieval fails
        ValueError: If no assets found
    """
    logger.info(f"Retrieving assets for query: {usn}")
    assets = await search_assets(jwt_token, usn)

    if not assets:
        raise ValueError("No news flashes found")

    # Convert to SelectableAsset - ALL START AS INCLUDED (matches LangGraph)
    selectable_assets = [
        SelectableAsset(**a.model_dump(), included=True)
        for a in assets
    ]

    # Preserve original asset order for regenerations (matches LangGraph)
    selectable_assets_original = [
        SelectableAsset(**a.model_dump(), included=True)
        for a in assets
    ]

    logger.info(f"Retrieved {len(selectable_assets)} assets, all marked as included")
    return selectable_assets, selectable_assets_original


def apply_asset_reordering(
    assets: List[SelectableAsset],
    asset_id: Optional[str],
    headline: Optional[str] = None
) -> None:
    """
    Apply asset_id or headline reordering in-place for first generation.

    Moves the specified asset to the front of the list to make it the lead alert.
    Priority: asset_id match first, then headline match if asset_id not provided.

    Args:
        assets: List of assets to reorder (modified in-place)
        asset_id: ID of asset to move to front position, or None to skip
        headline: Headline to match against asset headlines, or None to skip
    """
    # Priority 1: Try asset_id match (most specific)
    if asset_id:
        logger.info(f"First generation: reordering assets with asset_id={asset_id}")
        for i, asset in enumerate(assets):
            if asset.id == asset_id:
                selected = assets.pop(i)
                assets.insert(0, selected)
                logger.info(f"Moved asset {asset_id} to lead position")
                return

    # Priority 2: Try headline match (fallback when no asset_id)
    if headline:
        logger.info(f"First generation: attempting to match headline: {headline[:50]}...")
        headline_normalized = headline.strip().lower()

        for i, asset in enumerate(assets):
            if asset.headline:
                asset_headline_normalized = asset.headline.strip().lower()
                if asset_headline_normalized == headline_normalized:
                    selected = assets.pop(i)
                    assets.insert(0, selected)
                    logger.info(f"Moved asset matching headline to lead position: {asset.headline}")
                    return

        logger.info("No asset found matching the provided headline")
