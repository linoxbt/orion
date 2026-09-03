"""Which language a call is held in, and which voice can hold it.

Universal-3.5 Pro transcribes 18 languages natively and code-switches between
them with no configuration, so the transcription half of a multilingual call is
free. The two things that are not free are picking a voice that doesn't sound
foreign reading the language, and telling the agent which language to actually
speak - a model given an English system prompt will answer in English however
well it understood the question.
"""

# Voice ids come from AssemblyAI's catalog. Language-specific voices use a
# native accent and still code-switch with English, which matters on a support
# line where product names and plan names stay in English.
LANGUAGE_VOICES: dict[str, str] = {
    "en": "anna",
    "es": "lola",
    "fr": "estelle",
    "de": "juergen",
    "it": "giovanni",
    "pt": "rafael",
}

# The 18 Universal-3.5 Pro handles natively. Anything outside this falls back
# to Universal-2 for transcription, which still works - it just loses the
# code-switching, so it is worth being honest about the list.
SUPPORTED = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "tr": "Turkish",
    "hi": "Hindi",
    "vi": "Vietnamese",
    "ar": "Arabic",
    "he": "Hebrew",
    "ja": "Japanese",
    "zh": "Chinese",
}


def name_for(code: str) -> str:
    return SUPPORTED.get(code, "English")


def voice_for(code: str, default: str) -> str:
    """A voice that can hold the call. Falls back to the configured default
    rather than guessing at an id - an invented voice id is rejected outright
    at session.update, which would fail the call rather than degrade it."""
    return LANGUAGE_VOICES.get(code, default)


def instruction_for(code: str) -> str:
    """What to add to the system prompt so the agent actually speaks it."""
    if code == "en":
        return ""
    language = name_for(code)
    return (
        f" Conduct this entire call in {language}. Speak {language} from your first word, "
        "including the greeting. If the representative switches to another language, "
        f"follow them, then return to {language}. Keep company names, plan names and "
        "reference numbers in their original form rather than translating them."
    )
