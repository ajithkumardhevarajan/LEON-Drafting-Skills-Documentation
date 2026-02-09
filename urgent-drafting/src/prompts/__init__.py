"""Reuters style prompts for urgent drafting"""

from .intent_interpreter_prompts import (
    get_review_response_prompt,
    get_refinement_instructions_prompt
)

__all__ = [
    "get_review_response_prompt",
    "get_refinement_instructions_prompt",
]
