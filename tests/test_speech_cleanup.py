from ember_app.brain.speech import clean_assistant_text


def test_removes_stage_directions_and_markdown_emphasis():
    text = "[smiles] *Yep*, I'm awake now. [softly] **Ready when you are.**"

    assert clean_assistant_text(text) == "Yep, I'm awake now. Ready when you are."


def test_removes_parenthetical_roleplay_actions():
    text = "(I lean forward slightly in my chair, resting an elbow on the desk.) What's up?"

    assert clean_assistant_text(text) == "What's up?"


def test_preserves_non_stage_parentheses():
    text = "Use Python 3.12 (or newer) for this project."

    assert clean_assistant_text(text) == "Use Python 3.12 (or newer) for this project."


def test_removes_code_blocks_from_spoken_text():
    text = "I found it.\n```json\n{\"name\":\"tool\"}\n```\nShort version: done."

    assert clean_assistant_text(text) == "I found it.\nShort version: done."
