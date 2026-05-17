from nexus_core.response_text import speech_text


def test_speech_text_expands_file_names():
    spoken = speech_text("Abra `README.md` e depois nexus_core/response_text.py")

    assert "read me" in spoken.lower()
    assert "Markdown" in spoken
    assert "response text" in spoken
    assert "Python" in spoken


def test_speech_text_expands_common_tech_terms():
    spoken = speech_text("FastAPI, systemd, SQLite e NEXUS estão online.")

    assert "Fast A P I" in spoken
    assert "sístem D" in spoken
    assert "S Q Lite" in spoken
    assert "Néxus" in spoken


def test_speech_text_expands_model_names():
    spoken = speech_text("Usando qwen2.5:3b e gemma4:31b-cloud.")

    assert "Qwen 2.5, 3 B" in spoken
    assert "Guéma 4, 31 B cloud" in spoken
