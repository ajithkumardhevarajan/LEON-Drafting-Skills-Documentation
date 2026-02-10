"""Pydantic models for intent interpretation structured outputs"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class ReviewResponse(BaseModel):
    """Structured response for review interpretation

    This model defines the exact structure the LLM must return when
    interpreting user feedback on a spot story draft.
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


class StoryUpdateOutput(BaseModel):
    """Structured output for story updates"""
    updated_story: str = Field(
        description="The updated story body without headline or bullets"
    )
    advisory: str = Field(
        description="Advisory describing changes made to the story (max 25 words)"
    )


class UpdateModeSelection(BaseModel):
    """Structured response for update mode selection"""
    mode: Literal["add_background", "story_rewrite"] = Field(
        description="Update mode: add_background (keep existing lede, add info to body) or story_rewrite (rewrite lede with new info)"
    )


class SpotStoryRequest(BaseModel):
    """Extracted parameters from user's spot story generation request.

    The LLM extracts structured information from the user's natural language
    request to generate a spot story.
    """
    content_sources: str = Field(
        description="The main content to generate the story from. This could be a press release, "
                    "story idea, facts, quotes, or any source material the user provided. "
                    "Extract and include ALL relevant information from the user's message."
    )
    use_archive: bool = Field(
        default=False,
        description="Whether the user wants to search the archive for background/context. "
                    "True if user mentions: archive, background, previous stories, context, history, etc."
    )
    archive_query: Optional[str] = Field(
        default=None,
        description="Search query for archive if use_archive is True. "
                    "Extract key entities/topics (company names, people, events) for searching."
    )
    story_topic: str = Field(
        description="Brief topic/subject of the story (2-5 words) for logging and context"
    )


class StoryUpdateRequest(BaseModel):
    """Extracted parameters from user's story update request."""
    usn: str = Field(
        description="The USN (unique story number) of the existing story to update. "
                    "Format is typically alphanumeric like 'LXN3VG03Q'."
    )
    new_content: str = Field(
        description="The new information to add or update in the story. "
                    "Extract all relevant new facts, quotes, or developments."
    )
    use_archive: bool = Field(
        default=False,
        description="Whether to search archive for additional background"
    )
    archive_query: Optional[str] = Field(
        default=None,
        description="Search query for archive if use_archive is True"
    )
