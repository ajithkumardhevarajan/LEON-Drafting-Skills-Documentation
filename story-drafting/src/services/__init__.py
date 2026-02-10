"""Services module for story drafting MCP skill."""

from shared.llm import LLMOrchestrator
from ..config.llm_skill_config import load_llm_config
from .asset_api import search_assets, fetch_story_by_usn, search_archive_stories
from .intent_interpreter import IntentInterpreter, get_intent_interpreter
from .intent_models import (
    ReviewResponse,
    RefinementInstructions,
    StoryUpdateOutput,
    UpdateModeSelection,
)

# Global singleton instance
_llm_orchestrator = None


def get_llm_orchestrator() -> LLMOrchestrator:
    """Get global LLM orchestrator instance"""
    global _llm_orchestrator
    if _llm_orchestrator is None:
        config = load_llm_config()
        _llm_orchestrator = LLMOrchestrator(config)
    return _llm_orchestrator


__all__ = [
    "LLMOrchestrator",
    "get_llm_orchestrator",
    "search_assets",
    "fetch_story_by_usn",
    "search_archive_stories",
    "IntentInterpreter",
    "get_intent_interpreter",
    "ReviewResponse",
    "RefinementInstructions",
    "StoryUpdateOutput",
    "UpdateModeSelection",
]
