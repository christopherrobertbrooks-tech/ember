from ember_app.brain.manual_tool_parser import extract_manual_tool_calls


def test_extracts_tool_call_from_markdown_json_block():
    text = """```json
{"name": "web_search", "arguments": {"query": "2006 Honda Shadow VLX wiring harness"}}
```"""

    assert extract_manual_tool_calls(text) == [
        {
            "name": "web_search",
            "arguments": {"query": "2006 Honda Shadow VLX wiring harness"},
        }
    ]


def test_extracts_openai_style_tool_call():
    text = '{"function": {"name": "open_browser", "arguments": {"url": "https://example.com"}}}'

    assert extract_manual_tool_calls(text) == [
        {
            "name": "open_browser",
            "arguments": {"url": "https://example.com"},
        }
    ]
