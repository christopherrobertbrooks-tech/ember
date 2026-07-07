from phidata_engine import resolve_openai_endpoint


def test_resolve_openai_endpoint_prefers_lm_studio_endpoint():
    config = {
        "llama_server_url": "http://example.test:11434/v1",
        "lm_studio_endpoint": "http://example.test:1234/v1",
    }

    assert resolve_openai_endpoint(config) == "http://example.test:1234/v1"


def test_resolve_openai_endpoint_falls_back_to_llama_server_url():
    config = {"llama_server_url": "http://example.test:1234/v1"}

    assert resolve_openai_endpoint(config) == "http://example.test:1234/v1"
