"""Pydantic models for intent interpretation structured outputs"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class ReviewResponse(BaseModel):
    """Structured response for review interpretation

    This model defines the exact structure the LLM must return when
    interpreting user feedback on an urgent draft.

    Note: Asset selection is handled by the UI component, not here.
    """
    action: Literal["approve", "regenerate", "refine", "cancel"] = Field(
        description="User's intended action: approve the draft, regenerate a new version, refine with changes, or cancel"
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Refinement instructions - only for 'refine' action"
    )


class RefinementInstructions(BaseModel):
    """Structured refinement instructions

    This model defines how refinement requests should be parsed and structured.
    """
    target: Literal["headline", "body", "both"] = Field(
        description="Which part of the draft to modify: headline only, body only, or both"
    )
    change_type: Literal[
        "shorten", "expand", "rephrase", "fix", "tone", "restructure", "specific", "general"
    ] = Field(
        description="Category of change: shorten (reduce length), expand (add detail), rephrase (reword), "
                    "fix (correct errors), tone (adjust style), restructure (reorganize), "
                    "specific (exact changes), general (unclear/broad request)"
    )
    instructions: str = Field(
        description="Clear, specific, actionable instructions for the refinement. "
                    "Convert vague requests into concrete actions."
    )
    specific_changes: Optional[List[str]] = Field(
        default=None,
        description="List of specific edits if user mentioned exact changes (word replacements, deletions, additions)"
    )
