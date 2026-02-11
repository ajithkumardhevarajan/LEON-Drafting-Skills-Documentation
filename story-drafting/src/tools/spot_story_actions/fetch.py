"""Fetch existing story by USN for story updates"""

import logging
from typing import Optional

from ...models import Asset
from ...services.asset_api import fetch_story_by_usn

logger = logging.getLogger(__name__)


async def fetch_existing_story(
    auth_token: str,
    usn: str
) -> Optional[Asset]:
    """
    Fetch an existing published story by USN.

    Args:
        auth_token: JWT token for authentication
        usn: Unique Story Number (e.g., "LXN3VG03Q")

    Returns:
        Asset object if found, None otherwise
    """
    logger.info(f"Fetching existing story with USN: {usn}")

    try:
        asset = await fetch_story_by_usn(auth_token, usn)

        if asset:
            logger.info(f"Found story: {asset.headline[:50]}...")
            return asset
        else:
            logger.warning(f"No story found with USN: {usn}")
            return None

    except Exception as e:
        logger.error(f"Failed to fetch story with USN {usn}: {str(e)}")
        raise
