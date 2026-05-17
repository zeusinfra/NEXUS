from nexus_core.models.ollama_client import (
    OllamaClient,
    OllamaModel,
    choose_local_model,
)


def test_choose_local_model_prefers_known_small_model():
    assert choose_local_model(["llama3:8b", "qwen2.5:3b"]) == "qwen2.5:3b"


def test_choose_local_model_falls_back_to_small_token():
    assert choose_local_model(["custom:7b", "tiny-mini"]) == "tiny-mini"


def test_choose_local_model_returns_none_without_models():
    assert choose_local_model([]) is None


def test_ollama_status_selects_model_from_api(monkeypatch):
    client = OllamaClient()
    monkeypatch.setattr(client, "binary_path", lambda: "/usr/bin/ollama")
    monkeypatch.setattr(client, "list_models", lambda: [OllamaModel(name="qwen2.5:3b")])

    status = client.status()

    assert status.ready is True
    assert status.binary_found is True
    assert status.api_ok is True
    assert status.selected_model == "qwen2.5:3b"
