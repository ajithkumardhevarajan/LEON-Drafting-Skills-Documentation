"""Prompts module for story drafting MCP skill."""

from .spot_story_prompts import (
    BODY_PROMPT,
    HEADLINE_PROMPT,
    BULLET_POINTS_PROMPT,
    REFERENCES_PROMPT,
    REFINEMENT_PROMPT,
    STORY_UPDATE_BODY_PROMPT,
)
from .intent_interpreter_prompts import (
    get_review_response_prompt,
    get_refinement_instructions_prompt,
    get_update_mode_selection_prompt,
)

__all__ = [
    "BODY_PROMPT",
    "HEADLINE_PROMPT",
    "BULLET_POINTS_PROMPT",
    "REFERENCES_PROMPT",
    "REFINEMENT_PROMPT",
    "STORY_UPDATE_BODY_PROMPT",
    "get_review_response_prompt",
    "get_refinement_instructions_prompt",
    "get_update_mode_selection_prompt",
]
