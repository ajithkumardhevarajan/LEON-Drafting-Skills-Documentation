"""Intent Interpreter Service for natural language understanding"""

import json
import logging
import re
from typing import Dict, Any, List

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
        Interpret user's response to urgent review.

        Args:
            user_response: User's response (string, dict, or other)
            context: Context including urgent, assets, headline, body

        Returns:
            Dict with:
            - action: "approve" | "regenerate" | "refine" | "cancel"
            - assets: Updated asset array if user wants to change selection
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
                    logger.info(f"Parsed JSON response: {parsed.get('action')}, has assets: {'assets' in parsed}")
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass  # Not JSON, continue to keyword fallback

        # For now, rely on structured button responses from UI
        # Natural language interpretation is commented out for simpler debugging
        response_text = str(user_response)
        logger.info(f"Received non-dict response (fallback): {response_text[:100]}")

        # # LLM interpretation - COMMENTED OUT
        # assets = context.get("assets", [])
        # logger.info(f"Interpreting natural language response: {response_text[:100]}...")
        #
        # # Build interpretation prompt
        # interpretation_prompt = f"""
        # You are interpreting user feedback on a generated urgent news draft with {len(assets)} source news flashes.
        #
        # User response: "{response_text}"
        #
        # Determine the user's intent:
        #
        # 1. Action (required):
        #    - "approve": User is satisfied (e.g., "looks good", "perfect", "approve", "ok", "ship it", "great", "fine")
        #    - "regenerate": User wants a new version (e.g., "try again", "regenerate", "redo", "different version")
        #    - "refine": User wants specific edits (e.g., "make it shorter", "change X to Y", "add more detail")
        #    - "cancel": User wants to stop (e.g., "cancel", "stop", "abort", "nevermind")
        #
        # 2. Asset changes (only for regenerate):
        #    - If user mentions excluding/including specific news flashes (numbered 1 to {len(assets)})
        #    - Examples: "without 3", "exclude 2 and 4", "only use 1", "skip the last one", "just flash 2"
        #    - Parse numbers and determine which should be included/excluded
        #
        # 3. Instructions (only for refine):
        #    - The specific changes requested by the user
        #
        # Return ONLY valid JSON:
        # {{
        #     "action": "approve|regenerate|refine|cancel",
        #     "asset_changes": {{  // Only if changing selection for regenerate
        #         "exclude": [2, 4],  // Asset numbers to exclude
        #         "only": [1, 3]     // If user said "only use", list of assets to include
        #     }},
        #     "instructions": "refinement instructions if action is refine"
        # }}
        # """
        #
        # try:
        #     result = await self.llm.invoke(
        #         [{"role": "system", "content": interpretation_prompt}],
        #         temperature=0,
        #         model="gpt-4o"  # Use faster model for intent classification
        #     )
        #
        #     interpreted = json.loads(result)
        #     logger.info(f"Interpreted intent: {interpreted.get('action')}")
        #
        #     # Process asset changes if present
        #     if interpreted.get("asset_changes") and assets:
        #         asset_changes = interpreted["asset_changes"]
        #         updated_assets = []
        #
        #         # Determine which assets to include
        #         if asset_changes.get("only"):
        #             # User said "only use X" - include only those
        #             only_numbers = set(asset_changes["only"])
        #             for i, asset in enumerate(assets, 1):
        #                 asset_dict = asset.dict() if hasattr(asset, 'dict') else asset
        #                 asset_dict["included"] = i in only_numbers
        #                 updated_assets.append(asset_dict)
        #         elif asset_changes.get("exclude"):
        #             # User said "exclude X" - exclude those
        #             exclude_numbers = set(asset_changes["exclude"])
        #             for i, asset in enumerate(assets, 1):
        #                 asset_dict = asset.dict() if hasattr(asset, 'dict') else asset
        #                 asset_dict["included"] = i not in exclude_numbers
        #                 updated_assets.append(asset_dict)
        #
        #         if updated_assets:
        #             interpreted["assets"] = updated_assets
        #             logger.info(f"Updated {len([a for a in updated_assets if a['included']])} assets included")
        #
        #     return interpreted
        #
        # except Exception as e:
        #     logger.error(f"Failed to interpret with LLM, using fallback: {e}")

        # Simple keyword-based fallback for non-structured responses
        response_lower = response_text.lower()

        if any(w in response_lower for w in ["approve", "good", "perfect", "yes", "ok", "great", "fine", "ship"]):
            return {"action": "approve"}
        elif any(w in response_lower for w in ["cancel", "stop", "abort", "nevermind"]):
            return {"action": "cancel"}
        elif any(w in response_lower for w in ["regenerate", "again", "redo", "retry", "different"]):
            # Check for asset exclusions in natural language
            exclude_pattern = r"without (\d+)|exclude (\d+)|skip (\d+)|remove (\d+)"
            matches = re.findall(exclude_pattern, response_lower)
            if matches:
                # Flatten and filter matches
                excluded_nums = [int(m) for group in matches for m in group if m]
                return {"action": "regenerate", "exclude_assets": excluded_nums}
            return {"action": "regenerate"}
        else:
            # Default to refine with full text as instructions
            return {"action": "refine", "instructions": response_text}

    async def interpret_refinement_instructions(
        self,
        user_response: Any
    ) -> Dict[str, Any]:
        """
        Extract clear refinement instructions from user response

        Args:
            user_response: User's response

        Returns:
            Dict with:
            - instructions: Clear refinement instructions
            - target: "headline" | "body" | "both"
        """

        if isinstance(user_response, dict):
            return user_response

        response_text = str(user_response)

        # Determine target
        target = "both"
        response_lower = response_text.lower()
        if "headline" in response_lower and "body" not in response_lower:
            target = "headline"
        elif "body" in response_lower or "text" in response_lower or "paragraph" in response_lower:
            if "headline" not in response_lower:
                target = "body"

        logger.info(f"Refinement target: {target}")

        return {
            "instructions": response_text,
            "target": target
        }


# Global singleton
_intent_interpreter = None


def get_intent_interpreter() -> IntentInterpreter:
    """Get global intent interpreter instance"""
    global _intent_interpreter
    if _intent_interpreter is None:
        _intent_interpreter = IntentInterpreter()
    return _intent_interpreter
