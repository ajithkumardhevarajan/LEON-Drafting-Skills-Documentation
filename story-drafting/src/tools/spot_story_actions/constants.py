"""Shared constants for spot story drafting actions"""

# Action types
ACTION_APPROVE = "approve"
ACTION_REGENERATE = "regenerate"
ACTION_REFINE = "refine"
ACTION_CANCEL = "cancel"
ACTION_CREATE_DRAFT = "create_draft"

# Interrupt types
INTERRUPT_TYPE_REVIEW = "spot_story.review"
INTERRUPT_TYPE_ASSETS_SELECTION = "spot_story.assets_selection"
INTERRUPT_TYPE_UPDATE_MODE = "spot_story_update.mode_selection"
INTERRUPT_TYPE_REFINEMENT = "spot_story.refinement"
INTERRUPT_TYPE_REQUEST_INFO = "spot_story.request_info"

# Sentinel value sent by frontend Skip button to bypass CopilotKit's truthy check
SKIP_SENTINEL = "__SKIP__"

# Model configuration constants
MODEL_GEMINI_2_5_PRO = "gemini-2-5-pro"
MODEL_GPT4 = "gpt-4-1"
MODEL_GPT4O = "gpt-4o"
TEMPERATURE = 0.1
TEMPERATURE_LOW = 0.05

# Google Gemini thinking configuration
GEMINI_EXTRA_BODY = {
    "google": {
        "thinking_config": {
            "thinking_budget": 1000,
            "include_thoughts": False,
        }
    }
}
