"""Reuters Text Archive Search Tool for historical article queries"""

import asyncio
import httpx
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import BaseTool
from ..models import ToolResult

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Look for .env file in the project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # dotenv is not installed, just use system environment variables
    pass


class ArchiveSearchConfig:
    """Configuration for Reuters Text Archive API"""

    # OAuth credentials
    CLIENT_ID = os.getenv("REUTERS_ARCHIVE_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("REUTERS_ARCHIVE_CLIENT_SECRET", "")
    AUDIENCE = "4488c953-2cc1-445e-97e8-22fdc9388b5d"

    # API endpoints
    AUTH_URL = "https://auth-nonprod.thomsonreuters.com/oauth/token"
    API_BASE_URL = "https://archiveqa.us.dev.85556.aws-int.thomsonreuters.com/v1"

    # Polling configuration (3 minutes = 36 attempts * 5 seconds)
    MAX_RETRIES = 36
    RETRY_INTERVAL = 5  # seconds
    HISTORY_LENGTH = 1

    @classmethod
    def is_configured(cls) -> bool:
        """Check if the configuration has valid credentials"""
        return (
            cls.CLIENT_ID != "your_client_id_here" and
            cls.CLIENT_SECRET != "your_client_secret_here" and
            isinstance(cls.CLIENT_ID, str) and cls.CLIENT_ID.strip() != "" and
            isinstance(cls.CLIENT_SECRET, str) and cls.CLIENT_SECRET.strip() != ""
        )


class ArchiveSearchTool(BaseTool):
    """Tool to search Reuters Text Archive for historical articles and news"""

    @property
    def name(self) -> str:
        return "search_reuters_text_archive"

    @property
    def description(self) -> str:
        return """Searches the Reuters Text Archive for historical articles, news coverage, and background research.

        This tool can answer questions about:
        - Company strategies and developments (e.g., "What are the key points of Ford's EV strategy?")
        - Historical events and news coverage (e.g., "COVID-19 pandemic coverage in March 2020")
        - Political developments and elections (e.g., "Latest presidential election results")
        - Market and sector analysis (e.g., "Energy sector updates regarding renewable energy")
        - Entity-specific news with date ranges (e.g., "Trump administration news from January to March 2025")
        - Background on key developments (e.g., "Developments affecting the U.S. Inflation Reduction Act")

        The tool searches Reuters' extensive archive and returns comprehensive answers with references to original articles.
        It handles ambiguous queries by requesting clarification from the user."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "The user's natural language question or search query. This should be the user's latest message, not the entire chat history. Examples: 'What are the key points of Ford's EV strategy?', 'Summarize news for Disney', 'Hurricane coverage from Atlantic season 2024'",
                "required": True,
                "ui_metadata": {
                    "display_name": "Search Query",
                    "input_type": "text",
                    "placeholder": "e.g., What are the latest developments on climate policy?",
                    "help_text": "Enter your question about historical Reuters articles or news coverage"
                }
            }
        }

    @property
    def response_mode(self) -> str:
        return "direct"  # Return direct response from archive API without LLM processing

    async def _fetch_oauth_token(self, client: httpx.AsyncClient) -> str:
        """Fetch OAuth token from Thomson Reuters auth endpoint"""
        payload = {
            "client_id": ArchiveSearchConfig.CLIENT_ID,
            "client_secret": ArchiveSearchConfig.CLIENT_SECRET,
            "audience": ArchiveSearchConfig.AUDIENCE,
            "grant_type": "client_credentials"
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = await client.post(
                ArchiveSearchConfig.AUTH_URL,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise Exception("No access token returned from auth endpoint")

            return access_token
        except Exception as e:
            raise Exception(f"Failed to fetch OAuth token: {str(e)}")

    async def _submit_search_query(
        self, client: httpx.AsyncClient, access_token: str, query: str
    ) -> str:
        """Submit search query and get task ID"""
        api_url = f"{ArchiveSearchConfig.API_BASE_URL}/message:send"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "message": {
                "content": [
                    {
                        "text": query
                    }
                ]
            }
        }

        try:
            response = await client.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            task_id = result.get("task", {}).get("id")

            if not task_id:
                raise Exception("No task ID returned from archive API")

            return task_id
        except Exception as e:
            raise Exception(f"Failed to submit search query: {str(e)}")

    async def _fetch_task_result(
        self, client: httpx.AsyncClient, access_token: str, task_id: str
    ) -> Dict[str, Any]:
        """Fetch task result with polling"""
        api_url = f"{ArchiveSearchConfig.API_BASE_URL}/tasks/{task_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        params = {
            "historyLength": ArchiveSearchConfig.HISTORY_LENGTH
        }

        for attempt in range(ArchiveSearchConfig.MAX_RETRIES):
            if attempt > 0:
                # Wait before retrying
                await asyncio.sleep(ArchiveSearchConfig.RETRY_INTERVAL)

            try:
                response = await client.get(
                    api_url,
                    headers=headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()

                task_details = response.json()
                task_state = task_details.get("status", {}).get("state")

                # Check if task is completed (not in working or submitted state)
                if task_state and task_state not in ["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"]:
                    return task_details

            except Exception as e:
                # Continue polling even if a single request fails
                if attempt == ArchiveSearchConfig.MAX_RETRIES - 1:
                    raise Exception(f"Failed to fetch task result after {ArchiveSearchConfig.MAX_RETRIES} attempts: {str(e)}")
                continue

        # Timeout reached
        raise TimeoutError("The archive search took longer than expected. Please try again later.")

    def _extract_answer_from_result(self, task_result: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract the text answer and reference articles from the task result

        Returns:
            Tuple of (answer_text, references_list)
        """
        try:
            artifacts = task_result.get("artifacts", [])

            if not artifacts:
                return "No results found in the archive for your query.", []

            # Get the first artifact's parts
            first_artifact = artifacts[0]
            parts = first_artifact.get("parts", [])

            if not parts:
                return "No answer content found in the archive response.", []

            # Get the text from the first part
            text_content = parts[0].get("text", "")

            if not text_content:
                return "Empty response received from the archive.", []

            # Extract reference articles from the second part (if available)
            references = []
            if len(parts) > 1:
                data_part = parts[1].get("data", {})
                articles_data = data_part.get("data", {})
                articles = articles_data.get("articles", [])

                # Format references with consistent structure
                for idx, article in enumerate(articles, start=1):
                    references.append({
                        "ref_id": idx,
                        "headline": article.get("title", article.get("headline", "No headline")),
                        "body": article.get("content", article.get("body", "")),
                        "source": article.get("source", "Reuters"),
                        "date": article.get("content_timestamp", article.get("versionCreated", article.get("date", ""))),
                        "url": article.get("connect_link", article.get("uri", ""))
                    })

            return text_content, references

        except Exception as e:
            return f"Error extracting answer from archive result: {str(e)}", []

    async def execute(
        self, arguments: Dict[str, Any], jwt_token: str
    ) -> ToolResult:
        """Execute the archive search tool"""

        # Validate configuration
        if not ArchiveSearchConfig.is_configured():
            return ToolResult(
                content=[{
                    "type": "text",
                    "text": "Error: Reuters Text Archive API credentials are not configured. Please set REUTERS_ARCHIVE_CLIENT_ID and REUTERS_ARCHIVE_CLIENT_SECRET environment variables."
                }],
                isError=True
            )

        # Get query from arguments
        query = arguments.get("query", "").strip()

        if not query:
            return ToolResult(
                content=[{
                    "type": "text",
                    "text": "Error: Search query is required."
                }],
                isError=True
            )

        try:
            # Create HTTP client with SSL verification disabled for QA environment
            async with httpx.AsyncClient(verify=False) as client:
                # Step 1: Fetch OAuth token
                access_token = await self._fetch_oauth_token(client)

                # Step 2: Submit search query and get task ID
                task_id = await self._submit_search_query(client, access_token, query)

                # Step 3: Poll for task completion (waits up to 3 minutes)
                task_result = await self._fetch_task_result(client, access_token, task_id)

                # Step 4: Extract answer and references from result
                answer, references = self._extract_answer_from_result(task_result)

                # Build content array with both text and references
                content = [{"type": "text", "text": answer}]

                # Add references if any were found
                if references:
                    content.append({
                        "type": "references",
                        "references": references
                    })

                return ToolResult(
                    content=content,
                    isError=False
                )

        except TimeoutError as e:
            return ToolResult(
                content=[{
                    "type": "text",
                    "text": str(e)
                }],
                isError=True
            )
        except Exception as e:
            return ToolResult(
                content=[{
                    "type": "text",
                    "text": f"Error searching Reuters Text Archive: {str(e)}"
                }],
                isError=True
            )
