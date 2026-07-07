import pytest
import os
from ember_engine import EmberCore

def test_engine_initialization():
    engine = EmberCore()
    assert engine.mood == "neutral"
    assert engine.energy == 5
    assert not engine.dnd_enabled
    assert engine.system_prompt != ""

def test_architect_mode_toggle():
    engine = EmberCore()
    initial_mode = engine.architect_mode
    
    # Toggle it
    engine.set_architect_mode(not initial_mode)
    assert engine.architect_mode != initial_mode
    
    # Revert it
    engine.set_architect_mode(initial_mode)
    assert engine.architect_mode == initial_mode

def test_complete_computer_control_defaults_off():
    engine = EmberCore()

    assert engine.complete_computer_control is False

def test_control_computer_blocked_when_toggle_off():
    engine = EmberCore()
    engine.complete_computer_control = False

    result = engine.execute_tool("control_computer", {"action": "wait", "amount": 0})

    assert "Complete computer control is turned off" in result

def test_generate_mixed_stream_returns_direct_reply_once(monkeypatch):
    engine = EmberCore()
    calls = []

    def fake_call_llama_server(messages, stream=False, tools=None):
        calls.append({"stream": stream, "tools": bool(tools)})
        assert not stream
        return {"message": {"role": "assistant", "content": "One concise answer.", "tool_calls": []}}

    monkeypatch.setattr(engine, "_call_llama_server", fake_call_llama_server)
    monkeypatch.setattr(engine, "generate_tts_chunk", lambda text: None)

    chunks = list(engine.generate_mixed_stream("what is your status"))
    text = "".join(chunk for kind, chunk in chunks if kind == "text")

    assert text == "One concise answer."
    assert calls == [{"stream": False, "tools": True}]
