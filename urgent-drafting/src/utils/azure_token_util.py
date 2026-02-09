"""Azure AD Token Generation Utility

This module provides functionality to generate Azure AD OAuth tokens
for authenticating with the LLM Orchestrator proxy service.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from azure.identity import ClientSecretCredential
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)


@dataclass
class AzureTokenConfig:
    """Configuration for Azure AD token generation"""
    tenant_id: str
    client_id: str
    client_secret: str
    resource: str  # Azure AD resource scope (e.g., api://xxx/.default)


class TokenCache:
    """Simple token cache with expiration tracking"""

    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    def get(self) -> Optional[str]:
        """Get cached token if still valid"""
        if self._token and self._expires_at:
            # Add 5-minute buffer before expiration
            if datetime.utcnow() < (self._expires_at - timedelta(minutes=5)):
                logger.debug("Using cached Azure token")
                return self._token
            else:
                logger.info("Cached Azure token expired")
        return None

    def set(self, token: str, expires_on: int):
        """Cache token with expiration timestamp"""
        self._token = token
        self._expires_at = datetime.fromtimestamp(expires_on)
        logger.debug(f"Cached Azure token, expires at {self._expires_at}")


# Global token cache
_token_cache = TokenCache()


async def generate_azure_token(config: AzureTokenConfig) -> Optional[str]:
    """
    Generate an Azure AD authentication token using client credentials.

    This function uses the OAuth 2.0 client credentials flow to obtain
    an access token for the LLM Orchestrator service. Tokens are cached
    and reused until they expire (typically ~1 hour).

    Args:
        config: Azure token configuration with tenant, client, secret, and resource

    Returns:
        The access token string, or None if generation fails
    """
    # Check cache first
    cached_token = _token_cache.get()
    if cached_token:
        return cached_token

    try:
        logger.info("Generating new Azure AD token for LLM Orchestrator")

        # Create credential using client secret
        credential = ClientSecretCredential(
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            client_secret=config.client_secret
        )

        # Get token for the specified resource scope
        token_result = credential.get_token(config.resource)

        if not token_result or not token_result.token:
            logger.error("Token generation returned empty result")
            return None

        # Cache the token
        _token_cache.set(token_result.token, token_result.expires_on)

        logger.info(
            f"Successfully generated Azure token "
            f"(length: {len(token_result.token)}, "
            f"expires: {datetime.fromtimestamp(token_result.expires_on)})"
        )

        return token_result.token

    except AzureError as e:
        logger.error(f"Azure authentication error: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating Azure token: {str(e)}", exc_info=True)
        return None
