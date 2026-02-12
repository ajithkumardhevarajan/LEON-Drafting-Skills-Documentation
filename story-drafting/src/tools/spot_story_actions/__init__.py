"""Spot Story Actions Module

This module contains modular action functions for spot story generation and updates.
"""

from .constants import (
    ACTION_APPROVE,
    ACTION_REGENERATE,
    ACTION_REFINE,
    ACTION_CANCEL,
    ACTION_CREATE_DRAFT,
    INTERRUPT_TYPE_REVIEW,
    INTERRUPT_TYPE_ASSETS_SELECTION,
    INTERRUPT_TYPE_UPDATE_MODE,
    INTERRUPT_TYPE_REFINEMENT,
    INTERRUPT_TYPE_REQUEST_INFO,
    SKIP_SENTINEL,
    MODEL_GEMINI_2_5_PRO,
    MODEL_GPT4,
    MODEL_GPT4O,
    TEMPERATURE,
    TEMPERATURE_LOW,
)

from .generate import (
    generate_body,
    generate_headline,
    generate_bullet_points,
    generate_references,
    generate_spot_story_content,
    format_background_sources_for_display,
)

from .refine import (
    refine_story_content,
    handle_refinement,
)

from .archive import (
    search_archive_assets,
    handle_asset_selection,
    convert_to_selectable_assets,
    get_selected_headlines,
)

from .fetch import (
    fetch_existing_story,
)

from .update_mode import (
    select_update_mode,
    UpdateMode,
)

from .update import (
    generate_updated_story_body,
    generate_updated_spot_story_content,
)

__all__ = [
    # Constants
    "ACTION_APPROVE",
    "ACTION_REGENERATE",
    "ACTION_REFINE",
    "ACTION_CANCEL",
    "ACTION_CREATE_DRAFT",
    "INTERRUPT_TYPE_REVIEW",
    "INTERRUPT_TYPE_ASSETS_SELECTION",
    "INTERRUPT_TYPE_UPDATE_MODE",
    "INTERRUPT_TYPE_REFINEMENT",
    "INTERRUPT_TYPE_REQUEST_INFO",
    "SKIP_SENTINEL",
    "MODEL_GEMINI_2_5_PRO",
    "MODEL_GPT4",
    "MODEL_GPT4O",
    "TEMPERATURE",
    "TEMPERATURE_LOW",
    # Generate
    "generate_body",
    "generate_headline",
    "generate_bullet_points",
    "generate_references",
    "generate_spot_story_content",
    "format_background_sources_for_display",
    # Refine
    "refine_story_content",
    "handle_refinement",
    # Archive
    "search_archive_assets",
    "handle_asset_selection",
    "convert_to_selectable_assets",
    "get_selected_headlines",
    # Fetch
    "fetch_existing_story",
    # Update Mode
    "select_update_mode",
    "UpdateMode",
    # Update
    "generate_updated_story_body",
    "generate_updated_spot_story_content",
]
