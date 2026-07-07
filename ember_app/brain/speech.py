import re


BRACKETED_STAGE_DIRECTION = re.compile(
    r"\[(?:laughs?|sighs?|smiles?|grins?|waves?|shrugs?|cheers?|pauses?|thinking|whispers?|"
    r"speaking|tone|softly|playfully|teasingly|sarcastically|warmly|nods?|looks?[^]]*)\]",
    re.IGNORECASE,
)

PARENTHETICAL_STAGE_DIRECTION = re.compile(
    r"\(\s*(?:"
    r"(?:i\s+)?(?:lean|leans|smile|smiles|grin|grins|laugh|laughs|sigh|sighs|wave|waves|shrug|shrugs|"
    r"nod|nods|look|looks|glance|glances|pause|pauses|whisper|whispers|chuckle|chuckles|tilt|tilts|"
    r"rest|rests|sit|sits|stand|stands|turn|turns|raise|raises|lower|lowers)\b"
    r"|(?:softly|warmly|playfully|teasingly|sarcastically|quietly|knowingly)\b"
    r").*?\)",
    re.IGNORECASE,
)


def clean_assistant_text(text):
    """Remove formatting that sounds awkward when spoken aloud."""
    if not text:
        return ""

    cleaned = str(text)
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = BRACKETED_STAGE_DIRECTION.sub("", cleaned)
    cleaned = PARENTHETICAL_STAGE_DIRECTION.sub("", cleaned)
    cleaned = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", cleaned)
    cleaned = cleaned.replace("*", "")
    cleaned = cleaned.replace("_", "")
    cleaned = cleaned.replace("~", "")
    cleaned = re.sub(r"[ \t]+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
    return cleaned.strip()
