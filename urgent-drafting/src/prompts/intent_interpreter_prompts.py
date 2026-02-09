"""Intent Interpreter Prompts for Natural Language Understanding

These prompts define how user responses are interpreted:
1. Review response interpretation - Understanding user feedback on drafts
2. Refinement instructions interpretation - Parsing refinement requests
"""


def get_review_response_prompt(response_text: str) -> str:
    """
    Generate prompt for interpreting user's review response.

    Note: Asset selection is handled by the UI component, not interpreted here.

    Args:
        response_text: The user's response text

    Returns:
        Formatted prompt string (structured output handles JSON schema)
    """
    return f"""Interpret user feedback on an urgent news draft.

USER RESPONSE: "{response_text}"

ACTIONS:
- "approve": User is satisfied and wants to proceed (e.g., "looks good", "perfect", "ok", "ship it", "yes", "lgtm")
- "regenerate": User wants a completely new version (e.g., "try again", "redo", "different version", "start over")
- "refine": User wants specific edits or changes (e.g., "make it shorter", "change X to Y", "add more detail", "fix the headline")
- "cancel": User wants to stop the process (e.g., "cancel", "stop", "abort", "quit", "nevermind")

FIELDS TO SET:
- action: (required) The user's intended action based on their feedback
- instructions: (optional) Only if action="refine" - capture the user's exact refinement request
"""


def get_refinement_instructions_prompt(response_text: str) -> str:
    """
    Generate prompt for interpreting refinement instructions.

    Args:
        response_text: The user's refinement instructions

    Returns:
        Formatted prompt string (structured output handles JSON schema)
    """
    return f"""Parse user's refinement request for an urgent news draft (headline + body).

USER INSTRUCTIONS: "{response_text}"

TARGET DETECTION:
- "headline": User mentions "headline" explicitly
- "body": User mentions "body", "text", "paragraph", or "article"
- "both": General feedback or both parts mentioned

CHANGE TYPES:
- "shorten": Make concise, reduce length
- "expand": Add detail or context
- "rephrase": Reword without changing meaning
- "fix": Correct errors (typos, grammar, facts)
- "tone": Adjust style (formal, urgent, neutral, etc.)
- "restructure": Reorganize content
- "specific": Exact word/phrase changes mentioned
- "general": Unclear or broad request

INSTRUCTION CONVERSION (convert vague → specific):
- "make it punchier" → "Shorten sentences and use more impactful verbs"
- "too wordy" → "Remove unnecessary words and make more concise"
- "needs more context" → "Add background information and context"
- "make it shorter" → "Reduce length by removing unnecessary words while preserving key information"
- "fix the typo" → "Identify and correct spelling or grammatical errors"

SPECIFIC CHANGES:
Only populate if user explicitly mentions exact edits:
- Word replacements: "change X to Y"
- Deletions: "remove the part about X"
- Additions: "add information about X"

FIELDS TO SET:
- target: (required) Which part to modify
- change_type: (required) Category of change
- instructions: (required) Clear, actionable refinement steps
- specific_changes: (optional) List of exact edits if mentioned
"""
