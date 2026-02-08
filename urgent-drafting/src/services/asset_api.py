"""Asset API Client for searching news flashes"""

import httpx
import os
from typing import List, Dict, Any, Optional
import logging
from ..models import Asset

logger = logging.getLogger(__name__)


async def search_assets(
    auth_token: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None
) -> List[Asset]:
    """
    Search for assets using the Reuters GraphQL API

    Args:
        auth_token: JWT token for authentication
        query: USN or search keywords
        filters: Optional filters for the search

    Returns:
        List of Asset objects
    """
    api_url = "https://api.sphinx-test.thomsonreuters.com/search/v2/stories"
    api_key = os.getenv("REUTERS_API_KEY", "")

    # GraphQL query for searching stories
    graphql_query = """
    query ($searchInput: String, $filters: StoryFilters, $sort: Sort, $skip: Int, $take: Int) {
      stories(searchInput: $searchInput, filters: $filters, sort: $sort, skip: $skip, take: $take) {
        statistics {
          totalRecords
          executionTimeMs
        }
        records {
          data {
            asset {
              assetID
              headline
              sluglineTag
              usn
              editStatusString
              dateCreated
              dateModified
              textAssetType
              textBody
              priority
              wordCount
            }
          }
          highlight
        }
      }
    }
    """

    # Default filters for urgent drafting (matches original)
    if filters is None:
        filters = {
            "include": {
                "language": ["EN"],
                "textAssetType": ["Alert"],
                "editStatusString": ["Published"],
                "period": {"text": "anyTime"}
            }
        }

    # Variables for the GraphQL query
    variables = {
        "searchInput": query,
        "filters": filters,
        "skip": 0,
        "take": 50
    }

    # Prepare the request payload
    payload = {
        "query": graphql_query,
        "variables": variables
    }

    # Headers for the request
    headers = {
        "accept": "*/*",
        "accept-language": "en-CA,en-US;q=0.9,en;q=0.8",
        "authorization": f"Bearer {auth_token}",
        "content-type": "application/json",
        "origin": "https://sphinx-qa.int.thomsonreuters.com",
        "referer": "https://sphinx-qa.int.thomsonreuters.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (compatible; Claude-MCP-UrgentDrafting/1.0)",
        "x-api-key": api_key
    }

    logger.info(f"Searching assets with query: {query}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            # Parse the GraphQL response
            data = response.json()
            stories = data.get("data", {}).get("stories", {})
            records = stories.get("records", [])

            # Extract assets from the nested structure
            assets = []
            for record in records:
                asset_data = record.get("data", {}).get("asset", {})
                if asset_data and asset_data.get("headline"):
                    assets.append(Asset(
                        id=asset_data.get("assetID", ""),
                        headline=asset_data.get("headline", ""),
                        body=asset_data.get("textBody"),
                        modified_at=asset_data.get("dateModified"),
                        usn=asset_data.get("usn")
                    ))

            logger.info(f"Found {len(assets)} assets")
            return assets

    except httpx.HTTPError as e:
        logger.error(f"Asset search failed: {str(e)}")
        raise e
