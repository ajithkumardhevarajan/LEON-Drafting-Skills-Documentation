"""Intent Interpreter Service for natural language understanding"""

import json
import logging
from typing import Dict, Any

from ..prompts.intent_interpreter_prompts import (
    get_review_response_prompt,
    get_refinement_instructions_prompt
)
from .intent_models import ReviewResponse, RefinementInstructions

logger = logging.getLogger(__name__)


class IntentInterpreter:
    """Interprets user's natural language responses using LLM"""

    def __init__(self):
        # Import here to avoid circular dependency
        from .llm_orchestrator import get_llm_orchestrator
        self.llm = get_llm_orchestrator()

    async def interpret_review_response(
        self,
        user_response: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Interpret user's response to urgent review using structured outputs.

        Note: Asset selection is handled by the UI component, which sends
        back a sorted array in the user's desired order. This method only
        interprets the action (approve/regenerate/refine/cancel).

        Args:
            user_response: User's response (string, dict, or other)
            context: Context including urgent, assets, headline, body

        Returns:
            Dict with:
            - action: "approve" | "regenerate" | "refine" | "cancel"
            - instructions: Refinement instructions if action is refine
        """

        # Handle structured responses from UI
        if isinstance(user_response, dict):
            logger.info(f"Received structured response: {user_response.get('action')}")
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
        logger.info(f"Interpreting natural language response: {response_text[:100]}")

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


# Global singleton
_intent_interpreter = None


def get_intent_interpreter() -> IntentInterpreter:
    """Get global intent interpreter instance"""
    global _intent_interpreter
    if _intent_interpreter is None:
        _intent_interpreter = IntentInterpreter()
    return _intent_interpreter
