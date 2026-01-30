"""
Urgent Draft Tool Implementation

This tool demonstrates how to create urgent news drafts with different priority levels.
It shows:
- Optional parameters with sensible defaults (works without any parameters!)
- Enum validation for priority levels
- Structured news draft generation
- Proper error handling

This serves as a template for building more sophisticated urgent drafting tools.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from .base import BaseTool
from ..models import ToolResult

logger = logging.getLogger(__name__)


class UrgentDraftTool(BaseTool):
    """
    Tool for creating urgent news drafts.

    This tool demonstrates:
    - Optional parameters with defaults (works without any parameters)
    - Enum validation for priority levels (breaking, urgent, flash)
    - Parameter validation and fallback values
    - Structured draft generation with headline and body
    - Proper error handling
    """

    @property
    def name(self) -> str:
        return "create_urgent_draft"

    @property
    def description(self) -> str:
        return (
            "Creates an urgent news draft with specified priority level. "
            "Generates a headline and draft body based on the topic and priority. "
            "Supports breaking news, urgent alerts, and flash updates."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "topic": {
                "type": "string",
                "description": "The topic or subject for the urgent news draft",
                "default": "Breaking news event",
                "required": False,
            },
            "priority": {
                "type": "string",
                "description": "Priority level of the urgent draft",
                "enum": ["breaking", "urgent", "flash"],
                "default": "urgent",
                "required": False,
            },
            "word_count": {
                "type": "integer",
                "description": "Target word count for the draft body (50-500 words)",
                "default": 150,
                "required": False,
            },
        }

    async def execute(
        self, arguments: Dict[str, Any], jwt_token: str
    ) -> ToolResult:
        """
        Execute the urgent draft tool.

        Args:
            arguments: Dictionary with 'topic', 'priority', and 'word_count' parameters
            jwt_token: JWT token (can be used for authentication with external services)

        Returns:
            ToolResult with the urgent draft or error message
        """
        try:
            # Extract parameters with defaults
            topic = arguments.get("topic", "Breaking news event")
            if not topic or not topic.strip():
                topic = "Breaking news event"  # Fallback to default if empty

            priority = arguments.get("priority", "urgent").lower()
            word_count = arguments.get("word_count", 150)

            # Validate word count
            if not isinstance(word_count, int) or word_count < 50 or word_count > 500:
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": "Error: word_count must be an integer between 50 and 500",
                        }
                    ],
                    isError=True,
                )

            # Generate the draft
            draft = self._generate_draft(topic, priority, word_count)

            logger.info(
                f"Successfully generated {priority} draft for topic: {topic}"
            )

            return ToolResult(
                content=[{"type": "text", "text": draft}], isError=False
            )

        except Exception as e:
            logger.error(f"Error executing urgent draft tool: {str(e)}", exc_info=True)
            return ToolResult(
                content=[
                    {"type": "text", "text": f"Internal error: {str(e)}"}
                ],
                isError=True,
            )

    def _generate_draft(self, topic: str, priority: str, word_count: int) -> str:
        """
        Generate an urgent news draft.

        In a real implementation, this would:
        - Connect to news APIs or databases
        - Use AI/LLM services to generate content
        - Apply Reuters style guidelines
        - Include fact-checking and verification

        Args:
            topic: News topic
            priority: Priority level (breaking, urgent, flash)
            word_count: Target word count

        Returns:
            Formatted draft as string
        """
        # Get priority metadata
        priority_info = self._get_priority_info(priority)

        # Generate headline
        headline = self._generate_headline(topic, priority)

        # Generate draft body (simplified example)
        body = self._generate_body(topic, priority, word_count)

        # Get timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Format the complete draft
        draft_lines = [
            f"{'=' * 70}",
            f"{priority_info['label']}: {headline}",
            f"{'=' * 70}",
            f"",
            f"Priority: {priority_info['display']}",
            f"Generated: {timestamp}",
            f"Topic: {topic}",
            f"Target Length: {word_count} words",
            f"",
            f"{'─' * 70}",
            f"DRAFT BODY",
            f"{'─' * 70}",
            f"",
            body,
            f"",
            f"{'─' * 70}",
            f"",
            f"[END OF DRAFT]",
            f"",
            f"Note: This is a simulated draft for demonstration purposes.",
            f"In production, this would:",
            f"  • Connect to real news sources and databases",
            f"  • Use AI/LLM services for content generation",
            f"  • Apply Reuters editorial guidelines",
            f"  • Include fact-checking and verification steps",
            f"  • Support human-in-the-loop approval workflows",
        ]

        return "\n".join(draft_lines)

    def _get_priority_info(self, priority: str) -> Dict[str, str]:
        """Get display information for priority level."""
        priority_map = {
            "flash": {
                "label": "⚡ FLASH",
                "display": "FLASH (Highest Priority)",
                "prefix": "FLASH:",
            },
            "breaking": {
                "label": "🔴 BREAKING NEWS",
                "display": "BREAKING (High Priority)",
                "prefix": "BREAKING:",
            },
            "urgent": {
                "label": "🔵 URGENT",
                "display": "URGENT (Standard Priority)",
                "prefix": "URGENT:",
            },
        }
        return priority_map.get(priority, priority_map["urgent"])

    def _generate_headline(self, topic: str, priority: str) -> str:
        """
        Generate a headline based on topic and priority.

        In production, this would use AI/LLM or headline generation services.
        """
        # Simplified headline generation
        priority_info = self._get_priority_info(priority)

        # Basic headline formatting
        topic_words = topic.strip().split()
        if len(topic_words) > 8:
            # Truncate long topics
            headline_topic = " ".join(topic_words[:8]) + "..."
        else:
            headline_topic = topic.strip()

        return f"{priority_info['prefix']} {headline_topic}"

    def _generate_body(self, topic: str, priority: str, word_count: int) -> str:
        """
        Generate the draft body content.

        In production, this would:
        - Query news databases for context
        - Use LLM to generate appropriate content
        - Apply style guidelines
        - Include quotes and sources
        """
        # Simplified body generation for demonstration
        paragraphs = []

        # Lede paragraph
        paragraphs.append(
            f"[LEDE] A significant development regarding {topic} has emerged, "
            f"according to initial reports. This {priority} update provides preliminary "
            f"information on the situation as it unfolds."
        )

        # Context paragraph
        paragraphs.append(
            f"[CONTEXT] The situation concerning {topic} is currently developing. "
            f"Reuters is gathering additional information and verifying facts from "
            f"multiple sources to provide comprehensive coverage."
        )

        # Details paragraph
        paragraphs.append(
            f"[DETAILS] Further details about {topic} are expected as the story "
            f"develops. Our correspondents are working to confirm additional aspects "
            f"and will provide updates as verified information becomes available."
        )

        # Add note about word count
        current_text = "\n\n".join(paragraphs)
        current_word_count = len(current_text.split())

        if current_word_count < word_count:
            paragraphs.append(
                f"\n[ADDITIONAL REPORTING REQUIRED: Target {word_count} words, "
                f"current draft ~{current_word_count} words. Additional paragraphs "
                f"should include: background information, expert quotes, related "
                f"context, and impact analysis.]"
            )

        return "\n\n".join(paragraphs)
