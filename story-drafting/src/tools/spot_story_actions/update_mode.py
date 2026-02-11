"""Update mode selection for story updates

Handles user selection of update mode (add_background vs story_rewrite).
"""

import logging
from typing import Literal
from mcp_hitl import interrupt

from .constants import INTERRUPT_TYPE_UPDATE_MODE

logger = logging.getLogger(__name__)

UpdateMode = Literal["add_background", "story_rewrite"]


def select_update_mode() -> UpdateMode:
    """
    Prompt user to select update mode via interrupt.

    Returns:
        Selected update mode: "add_background" or "story_rewrite"
    """
    question = """How would you like to integrate this new information?
<ul>
<li>Choose <strong>add background</strong> to keep the existing lede unchanged and add the new information to the body as supporting context</li>
<li>Choose <strong>story rewrite</strong> to rewrite the lede with the new information as the primary driver and restructure the story</li>
</ul>"""

    logger.info("Requesting update mode selection from user")

    selected_mode = interrupt({
        "type": INTERRUPT_TYPE_UPDATE_MODE,
        "content": question,
    })

    # Parse the selection
    if isinstance(selected_mode, list):
        selected_mode = selected_mode[0].content if hasattr(selected_mode[0], 'content') else str(selected_mode[0])

    # Normalize the selection
    mode_str = str(selected_mode).lower().strip()

    if "rewrite" in mode_str or "story_rewrite" in mode_str:
        mode: UpdateMode = "story_rewrite"
    else:
        # Default to add_background
        mode = "add_background"

    logger.info(f"User selected update mode: {mode}")
    return mode
