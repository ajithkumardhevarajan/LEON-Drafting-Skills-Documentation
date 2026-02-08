"""Urgent regeneration logic"""

import logging
from typing import List, Optional, Dict, Any

from ...models import SelectableAsset

logger = logging.getLogger(__name__)


def handle_regeneration(
    feedback: Dict[str, Any],
    original_assets: List[SelectableAsset]
) -> Optional[List[SelectableAsset]]:
    """
    Process regeneration with updated asset selection and order.

    This function takes user feedback containing a new asset ordering and
    inclusion state, and creates a new list of SelectableAssets based on
    the original assets but with the user's specified changes.

    Args:
        feedback: User feedback containing updated asset selection in feedback["assets"]
        original_assets: Original asset list to use as base

    Returns:
        New list of SelectableAssets with updated order and inclusion, or None if no assets provided
    """
    if not feedback.get("assets"):
        return None

    logger.info("Updating asset selection and order based on user feedback")

    # Create new asset list from user's feedback - preserves user's order (matches LangGraph)
    new_assets = []
    for asset_update in feedback["assets"]:
        asset_id_from_feedback = asset_update.get("id")

        # Find original asset by ID
        for original in original_assets:
            if original.id == asset_id_from_feedback:
                # Create new SelectableAsset with updated inclusion state
                # Use model_dump(exclude={'included'}) to avoid duplicate 'included' keyword
                original_data = original.model_dump(exclude={'included'})
                new_asset = SelectableAsset(**original_data, included=asset_update.get("included", True))
                new_assets.append(new_asset)
                break

    # Log the updated selection
    included_count = sum(1 for a in new_assets if a.included)
    logger.info(f"Asset selection updated: {included_count}/{len(new_assets)} included in user-specified order")

    return new_assets
