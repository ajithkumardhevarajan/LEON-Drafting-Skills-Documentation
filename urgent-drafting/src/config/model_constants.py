"""Model Constants for LLM Orchestrator

Defines available models and their categories, similar to TypeScript llm.config.ts
"""

from enum import Enum
from typing import List, Set


class Models(str, Enum):
    """Available LLM models"""
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    O1_MINI = "o1-mini"
    O3_MINI = "o3-mini"
    O4_MINI = "o4-mini"
    GPT4_1 = "gpt-4-1"
    GEMINI_2_5_FLASH = "gemini-2-5-flash"
    GEMINI_2_5_PRO = "gemini-2-5-pro"
    CLAUDE35SONNET = "claude-3.5-sonnet"
    OPENARENA = "openarena"


class ModelCategories:
    """Model categorization for feature support detection"""

    OPENAI: Set[str] = {
        Models.GPT4O,
        Models.GPT4O_MINI,
        Models.O1_MINI,
        Models.O3_MINI,
        Models.O4_MINI,
        Models.GPT4_1,
    }

    GEMINI: Set[str] = {
        Models.GEMINI_2_5_FLASH,
        Models.GEMINI_2_5_PRO,
    }

    CLAUDE: Set[str] = {
        Models.CLAUDE35SONNET,
    }

    OPENARENA: Set[str] = {
        Models.OPENARENA,
    }

    # Mini models that don't support system messages
    MINI_MODELS: Set[str] = {
        Models.O1_MINI,
        Models.O3_MINI,
        Models.O4_MINI,
    }


def is_openai_model(model: str) -> bool:
    """Check if model is an OpenAI model"""
    return model in ModelCategories.OPENAI


def is_gemini_model(model: str) -> bool:
    """Check if model is a Gemini model"""
    return model in ModelCategories.GEMINI


def is_claude_model(model: str) -> bool:
    """Check if model is a Claude model"""
    return model in ModelCategories.CLAUDE


def is_openarena_model(model: str) -> bool:
    """Check if model is an OpenArena model"""
    return model in ModelCategories.OPENARENA


def uses_azure_orchestrator(model: str) -> bool:
    """Check if model uses Azure orchestrator"""
    return is_openai_model(model) or is_gemini_model(model)


def is_mini_model(model: str) -> bool:
    """Check if model is a mini model (no system message support)"""
    return model in ModelCategories.MINI_MODELS


def get_all_models() -> List[str]:
    """Get list of all available models"""
    return [model.value for model in Models]
