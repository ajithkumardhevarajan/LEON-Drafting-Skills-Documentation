"""Intent Interpreter Prompts for Natural Language Understanding

These prompts define how user responses are interpreted:
1. Review response interpretation - Understanding user feedback on spot story drafts
2. Refinement instructions interpretation - Parsing refinement requests
"""


def get_review_response_prompt(response_text: str) -> str:
    """
    Generate prompt for interpreting user's review response.

    Args:
        response_text: The user's response text

    Returns:
        Formatted prompt string (structured output handles JSON schema)
    """
    return f"""Interpret user feedback on a spot story draft.

USER RESPONSE: "{response_text}"

ACTIONS:
- "approve": User is satisfied and wants to proceed (e.g., "looks good", "perfect", "ok", "ship it", "yes", "lgtm", "publish", "ready")
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
    return f"""Parse user's refinement request for a spot story draft (headline + bullets + body).

USER INSTRUCTIONS: "{response_text}"

TARGET DETECTION:
- "headline": User mentions "headline" explicitly
- "body": User mentions "body", "text", "paragraph", "story", or "article"
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


def get_update_mode_selection_prompt() -> str:
    """
    Generate prompt for update mode selection interpretation.

    Returns:
        Formatted prompt string for understanding update mode choice
    """
    return """Interpret user's selection for how to integrate new information into an existing story.

UPDATE MODES:
- "add_background": Keep the existing lede unchanged, add new information to the body as supporting context
- "story_rewrite": Rewrite the lede with new information as the primary driver, restructure the story

The user has selected one of these options. Return the appropriate mode.
"""


def get_spot_story_request_prompt(user_message: str) -> str:
    """
    Generate prompt for extracting spot story generation parameters from user request.

    Args:
        user_message: The user's natural language request

    Returns:
        Formatted prompt string for parameter extraction
    """
    return f"""Extract spot story generation parameters from the user's request.

USER REQUEST: "{user_message}"

EXTRACTION RULES:

1. CONTENT SOURCES (required):
   - Extract ALL factual information the user wants in the story
   - Include: facts, figures, quotes, events, company names, people, dates, locations
   - Include the full context, not just keywords
   - If user provides a press release or document, include its key content
   - Example: "Write about Apple's $500B investment" → content_sources should be "Apple announced a $500 billion investment in the United States, creating 20,000 jobs focused on AI research and semiconductor manufacturing"

2. USE ARCHIVE (boolean):
   - Set to true if user mentions ANY of: "archive", "background", "context", "previous stories", "history", "related articles", "past coverage"
   - Set to false otherwise (default)

3. ARCHIVE QUERY (if use_archive=true):
   - Extract key searchable terms: company names, people names, topics, events
   - Keep it concise for search (3-6 words max)
   - Example: "Apple investment US" or "Tesla earnings Q4"

4. STORY TOPIC (required):
   - Brief 2-5 word topic for logging
   - Example: "Apple US investment" or "Tesla Q4 earnings"

IMPORTANT: The content_sources field should contain EVERYTHING the LLM needs to write the story.
Do not lose any information from the user's request.
"""


def get_story_update_request_prompt(user_message: str) -> str:
    """
    Generate prompt for extracting story update parameters from user request.

    Args:
        user_message: The user's natural language request

    Returns:
        Formatted prompt string for parameter extraction
    """
    return f"""Extract story update parameters from the user's request.

USER REQUEST: "{user_message}"

EXTRACTION RULES:

1. USN (required):
   - The unique story number to update
   - Format: alphanumeric like "LXN3VG03Q"
   - Look for patterns like "story LXN3VG03Q", "update LXN3VG03Q", "USN: LXN3VG03Q"

2. NEW CONTENT (required):
   - Extract ALL new information to add to the story
   - Include: new facts, updates, quotes, developments
   - Preserve full context and details

3. USE ARCHIVE (boolean):
   - Set to true if user wants additional background from archive
   - Default false

4. ARCHIVE QUERY (if use_archive=true):
   - Key search terms for finding related stories
"""
