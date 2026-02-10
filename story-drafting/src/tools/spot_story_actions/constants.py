"""Shared constants for spot story drafting actions"""

# Action types
ACTION_APPROVE = "approve"
ACTION_REGENERATE = "regenerate"
ACTION_REFINE = "refine"
ACTION_CANCEL = "cancel"

# Interrupt types
INTERRUPT_TYPE_REVIEW = "spot_story.review"
INTERRUPT_TYPE_ASSETS_SELECTION = "spot_story.assets_selection"
INTERRUPT_TYPE_UPDATE_MODE = "spot_story_update.mode_selection"
INTERRUPT_TYPE_REFINEMENT = "spot_story.refinement"

# Model configuration constants
MODEL_GEMINI_2_5_PRO = "gemini-2-5-pro"
MODEL_GPT4 = "gpt-4-1"
MODEL_GPT4O = "gpt-4o"
TEMPERATURE = 0.1
TEMPERATURE_LOW = 0.05
