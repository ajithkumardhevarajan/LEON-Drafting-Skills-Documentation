"""Semantic Search Service

This service handles communication with the Thomson Reuters semantic search API
to find relevant background articles for spot story generation.

The service manages:
- OAuth2 token acquisition and caching
- Search submission and polling
- Result parsing and mapping to Asset model
"""

import asyncio
import os
import time
import logging
from typing import List, Optional, Dict, Any
import httpx

from ..models import Asset

logger = logging.getLogger(__name__)

# Token cache
_token_cache: Optional[Dict[str, Any]] = None


class SemanticSearchError(Exception):
    """Base exception for semantic search errors"""
    pass


class TokenAcquisitionError(SemanticSearchError):
    """Failed to acquire OAuth2 token"""
    pass


class SearchSubmissionError(SemanticSearchError):
    """Failed to submit search request"""
    pass


class SearchTimeoutError(SemanticSearchError):
    """Search polling timed out"""
    pass


async def get_oauth_token() -> str:
    """
    Acquire OAuth2 token from auth server with caching.

    Tokens are cached in memory with expiry check (tokens typically last 24h).
    On expiry or first call, fetches a new token.

    Returns:
        Valid OAuth2 bearer token

    Raises:
        TokenAcquisitionError: If token acquisition fails
    """
    global _token_cache

    # Check cache
    if _token_cache:
        expires_at = _token_cache.get("expires_at", 0)
        if time.time() < expires_at:
            logger.debug("Using cached OAuth token")
            return _token_cache["access_token"]

    # Load credentials from environment (fetched from AWS Secrets Manager)
    client_id = os.getenv("SEMANTIC_SEARCH_CLIENT_ID")
    client_secret = os.getenv("SEMANTIC_SEARCH_CLIENT_SECRET")
    audience = os.getenv("SEMANTIC_SEARCH_AUDIENCE")

    if not client_id or not client_secret or not audience:
        raise TokenAcquisitionError(
            "Missing semantic search credentials. Ensure SEMANTIC_SEARCH_CLIENT_ID, "
            "SEMANTIC_SEARCH_CLIENT_SECRET, and SEMANTIC_SEARCH_AUDIENCE are set."
        )
    scope = (
        "https://api.tr.com/auth/reuters.semantic_search.write "
        "https://api.tr.com/auth/reuters.semantic_search.read"
    )
    auth_url = "https://auth-nonprod.thomsonreuters.com/oauth/token"

    # Request token
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
        "grant_type": "client_credentials",
        "scope": scope
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Acquiring OAuth token from {auth_url}")
            response = await client.post(
                auth_url,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            token_data = response.json()

            # Cache token with expiry (use 90% of expires_in for safety margin)
            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 86400)  # Default 24h
            expires_at = time.time() + (expires_in * 0.9)

            _token_cache = {
                "access_token": access_token,
                "expires_at": expires_at
            }

            logger.info("Successfully acquired OAuth token")
            return access_token

    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = e.response.text
        raise TokenAcquisitionError(
            f"Failed to acquire token (HTTP {e.response.status_code}): {error_detail}"
        ) from e
    except Exception as e:
        raise TokenAcquisitionError(f"Token acquisition failed: {str(e)}") from e


async def submit_search(query: str, token: str) -> str:
    """
    Submit a search request to the semantic search API.

    Args:
        query: Natural language search query (user content)
        token: OAuth2 bearer token

    Returns:
        Search ID for polling results

    Raises:
        SearchSubmissionError: If search submission fails
    """
    base_url = os.getenv(
        "SEMANTIC_SEARCH_BASE_URL",
        "https://semantic-search.dev.82056.aws-int.thomsonreuters.com"
    )

    search_url = f"{base_url}/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {"query": query}

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Submitting semantic search: {query[:100]}...")
            response = await client.post(
                search_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            search_id = result.get("search_id")
            if not search_id:
                raise SearchSubmissionError("No search_id in response")

            logger.info(f"Search submitted successfully, search_id: {search_id}")
            return search_id

    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
        except Exception:
            error_detail = e.response.text
        raise SearchSubmissionError(
            f"Search submission failed (HTTP {e.response.status_code}): {error_detail}"
        ) from e
    except Exception as e:
        raise SearchSubmissionError(f"Search submission failed: {str(e)}") from e


async def poll_search_results(
    search_id: str,
    token: str,
    poll_interval: int = 5,
    max_attempts: int = 12
) -> Dict[str, Any]:
    """
    Poll for search results until completion or timeout.

    Args:
        search_id: Search ID from submit_search
        token: OAuth2 bearer token
        poll_interval: Seconds between poll attempts (default: 10)
        max_attempts: Maximum number of poll attempts (default: 6 = 60s total)

    Returns:
        Complete search results payload

    Raises:
        SearchTimeoutError: If search doesn't complete within timeout
        SemanticSearchError: If search fails or returns error status
    """
    base_url = os.getenv(
        "SEMANTIC_SEARCH_BASE_URL",
        "https://semantic-search.dev.82056.aws-int.thomsonreuters.com"
    )

    results_url = f"{base_url}/search/{search_id}"
    headers = {"Authorization": f"Bearer {token}"}

    logger.info(f"Starting to poll for results (search_id: {search_id})")
    logger.info(f"Will poll every {poll_interval}s for up to {max_attempts * poll_interval}s until status is SUCCESS")

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    results_url,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()

                status = result.get("status")
                logger.info(f"Poll attempt {attempt}/{max_attempts}: status={status}")

                if status == "SUCCESS":
                    logger.info("✓ Search status is SUCCESS - returning results")
                    return result
                elif status in ("FAILED", "ERROR"):
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Search status is {status} - aborting")
                    raise SemanticSearchError(f"Search failed: {error_msg}")

                # Status is PENDING or IN_PROGRESS, continue polling
                logger.info(f"Status is {status} - waiting {poll_interval}s before next poll")
                if attempt < max_attempts:
                    await asyncio.sleep(poll_interval)
                else:
                    logger.warning(f"Max attempts reached with status {status}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text
            raise SemanticSearchError(
                f"Polling failed (HTTP {e.response.status_code}): {error_detail}"
            ) from e
        except SemanticSearchError:
            raise
        except Exception as e:
            logger.warning(f"Poll attempt {attempt} failed: {str(e)}")
            if attempt < max_attempts:
                await asyncio.sleep(poll_interval)
            else:
                raise SemanticSearchError(f"Polling failed: {str(e)}") from e

    # Timeout
    raise SearchTimeoutError(
        f"Search timed out after {max_attempts * poll_interval} seconds"
    )


def parse_and_flatten_results(results: Dict[str, Any]) -> List[Asset]:
    """
    Parse search results and flatten into list of Asset objects.

    Results have nested structure: results[].searches[].items[]
    This function flattens all items, sorts by timestamp (most recent first),
    and takes the top 5.

    Args:
        results: Complete search results payload from API

    Returns:
        List of up to 5 Asset objects, sorted by content_timestamp descending
    """
    all_items = []

    # Navigate nested structure: results -> searches -> items
    results_list = results.get("results", [])
    for result_group in results_list:
        searches = result_group.get("searches", [])
        for search in searches:
            items = search.get("items", [])
            all_items.extend(items)

    if not all_items:
        logger.info("No items found in search results")
        return []

    logger.info(f"Found {len(all_items)} total items across all sub-queries")

    # Sort by content_timestamp descending (most recent first)
    all_items.sort(
        key=lambda x: x.get("content_timestamp", ""),
        reverse=True
    )

    # Take top 5
    top_items = all_items[:5]

    # Map to Asset model
    assets = []
    for item in top_items:
        # Truncate body to ~500 chars for display
        body = item.get("content", "")
        if len(body) > 500:
            body = body[:497] + "..."

        asset = Asset(
            id=item.get("story_uid", ""),
            headline=item.get("title", "Untitled"),
            body=body,
            modified_at=item.get("content_timestamp"),
            usn=item.get("document_link")  # Closest equivalent to USN
        )
        assets.append(asset)

    logger.info(f"Returning top {len(assets)} assets")
    return assets


async def search_semantic(query: str) -> List[Asset]:
    """
    Orchestrated semantic search function.

    Performs complete workflow:
    1. Acquire OAuth token
    2. Submit search
    3. Poll for results
    4. Parse and flatten to top 5 assets

    This is the main entry point for semantic search.

    Args:
        query: Natural language search query (user's request)

    Returns:
        List of up to 5 Asset objects for user selection

    Raises:
        SemanticSearchError: If any step fails
    """
    logger.info(f"Starting semantic search workflow: {query[:100]}...")

    # Step 1: Get token
    token = await get_oauth_token()

    # Step 2: Submit search
    search_id = await submit_search(query, token)

    # Step 3: Poll for results
    results = await poll_search_results(search_id, token)

    # Step 4: Parse and flatten
    assets = parse_and_flatten_results(results)

    logger.info(f"Semantic search completed successfully with {len(assets)} results")
    return assets
