"""Intent Interpreter Service for natural language understanding"""

import json
import logging
from typing import Dict, Any

from ..prompts.intent_interpreter_prompts import (
    get_review_response_prompt,
    get_refinement_instructions_prompt,
    get_spot_story_request_prompt,
    get_story_update_request_prompt
)
from .intent_models import (
    ReviewResponse,
    RefinementInstructions,
    SpotStoryRequest,
    StoryUpdateRequest
)

logger = logging.getLogger(__name__)


class IntentInterpreter:
    """Interprets user's natural language responses using LLM"""

    def __init__(self):
        # Import here to avoid circular dependency
        from . import get_llm_orchestrator
        self.llm = get_llm_orchestrator()

    async def interpret_review_response(
        self,
        user_response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Interpret user's response to story review using structured outputs.

        Args:
            user_response: User's response (string, dict, or other)
            context: Context including story, assets, headline, body

        Returns:
            Dict with:
            - action: "approve" | "regenerate" | "refine" | "cancel"
            - instructions: Refinement instructions if action is refine
        """

        # Handle structured responses from UI
        if isinstance(user_response, dict):
            logger.info(f"✅ FAST-PATH: Received structured response: {user_response}")
            return user_response

        # Try to parse JSON string responses
        if isinstance(user_response, str):
            try:
                parsed = json.loads(user_response)
                if isinstance(parsed, dict) and 'action' in parsed:
                    logger.info(f"Parsed JSON response: {parsed.get('action')}")
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass  # Not JSON, continue to LLM interpretation

        # Use LLM structured output for natural language interpretation
        response_text = str(user_response)
        logger.info(f"🤖 LLM INTERPRETATION: Type={type(user_response).__name__}, Value={response_text[:100]}")

        # Build interpretation prompt
        interpretation_prompt = get_review_response_prompt(response_text)

        # Call LLM with structured output - guaranteed valid schema!
        try:
            result: ReviewResponse = await self.llm.invoke_structured(
                messages=[{"role": "system", "content": interpretation_prompt}],
                response_model=ReviewResponse,
                model="gpt-4-1",
                temperature=0
            )

            logger.info(f"Interpreted intent: {result.action}")

            # Convert Pydantic model to dict for backwards compatibility
            interpreted = {"action": result.action}

            # Add instructions if present (for refine action)
            if result.instructions:
                interpreted["instructions"] = result.instructions

            return interpreted

        except Exception as e:
            logger.error(f"Failed to interpret review response: {e}", exc_info=True)
            raise RuntimeError(f"Failed to interpret user response: {response_text[:100]}...") from e

    async def interpret_refinement_instructions(
        self,
        user_response: Any
    ) -> Dict[str, Any]:
        """
        Extract clear, actionable refinement instructions using structured outputs.

        Args:
            user_response: User's response (string, dict, or other)

        Returns:
            Dict with:
            - instructions: Clear, actionable refinement instructions
            - target: "headline" | "body" | "both"
            - change_type: Category of change (optional)
            - specific_changes: Detailed list of changes if identifiable (optional)
        """

        # Handle structured responses
        if isinstance(user_response, dict):
            logger.info(f"Received structured refinement: target={user_response.get('target')}")
            return user_response

        response_text = str(user_response)
        logger.info(f"Interpreting refinement instructions: {response_text[:100]}")

        # Build refinement interpretation prompt
        interpretation_prompt = get_refinement_instructions_prompt(response_text)

        # Call LLM with structured output - guaranteed valid schema!
        try:
            result: RefinementInstructions = await self.llm.invoke_structured(
                messages=[{"role": "system", "content": interpretation_prompt}],
                response_model=RefinementInstructions,
                model="gpt-4-1",
                temperature=0
            )

            logger.info(
                f"Interpreted refinement: target={result.target}, "
                f"type={result.change_type}, "
                f"specific_changes={len(result.specific_changes) if result.specific_changes else 0}"
            )

            # Convert Pydantic model to dict for backwards compatibility
            interpreted = {
                "target": result.target,
                "change_type": result.change_type,
                "instructions": result.instructions
            }

            # Add optional fields if present
            if result.specific_changes:
                interpreted["specific_changes"] = result.specific_changes

            return interpreted

        except Exception as e:
            logger.error(f"Failed to interpret refinement instructions: {e}", exc_info=True)
            raise RuntimeError(f"Failed to interpret refinement instructions: {response_text[:100]}...") from e

    async def interpret_spot_story_request(
        self,
        user_message: str
    ) -> SpotStoryRequest:
        """
        Extract spot story generation parameters from user's natural language request.

        Args:
            user_message: The user's request (e.g., "Write a spot story about...")

        Returns:
            SpotStoryRequest with extracted parameters
        """
        logger.info(f"Interpreting spot story request: {user_message[:100]}...")

        interpretation_prompt = get_spot_story_request_prompt(user_message)

        try:
            result: SpotStoryRequest = await self.llm.invoke_structured(
                messages=[{"role": "system", "content": interpretation_prompt}],
                response_model=SpotStoryRequest,
                model="gpt-4-1",
                temperature=0
            )

            logger.info(
                f"Extracted spot story params: topic='{result.story_topic}', "
                f"use_archive={result.use_archive}, "
                f"content_length={len(result.content_sources)}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to interpret spot story request: {e}", exc_info=True)
            raise RuntimeError(f"Failed to interpret spot story request: {user_message[:100]}...") from e

    async def interpret_story_update_request(
        self,
        user_message: str
    ) -> StoryUpdateRequest:
        """
        Extract story update parameters from user's natural language request.

        Args:
            user_message: The user's request (e.g., "Update story LXN3VG03Q with...")

        Returns:
            StoryUpdateRequest with extracted parameters
        """
        logger.info(f"Interpreting story update request: {user_message[:100]}...")

        interpretation_prompt = get_story_update_request_prompt(user_message)

        try:
            result: StoryUpdateRequest = await self.llm.invoke_structured(
                messages=[{"role": "system", "content": interpretation_prompt}],
                response_model=StoryUpdateRequest,
                model="gpt-4-1",
                temperature=0
            )

            logger.info(
                f"Extracted update params: usn='{result.usn}', "
                f"use_archive={result.use_archive}, "
                f"content_length={len(result.new_content)}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to interpret story update request: {e}", exc_info=True)
            raise RuntimeError(f"Failed to interpret story update request: {user_message[:100]}...") from e


# Global singleton
_intent_interpreter = None


def get_intent_interpreter() -> IntentInterpreter:
    """Get global intent interpreter instance"""
    global _intent_interpreter
    if _intent_interpreter is None:
        _intent_interpreter = IntentInterpreter()
    return _intent_interpreter
