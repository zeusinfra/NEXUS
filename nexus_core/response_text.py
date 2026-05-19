import re


_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n?(.*?)```", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_PATH_RE = re.compile(r"(?<!\w)(?:[~./\w-]+/)+[\w.-]+")
_FILE_RE = re.compile(
    r"\b[\w-]+\.(?:py|rs|toml|md|json|yaml|yml|txt|sh|deb|service|sqlite3|"
    r"log|lock|env|ini|cfg|conf|html|css|js|jsx|ts|tsx|go|sql|onnx|bin|wav|mp3)\b",
    re.I,
)

_TERM_PRONUNCIATION = {
    "NEXUS": "Néxus",
    "Linux": "Línux",
    "FastAPI": "Fast A P I",
    "API": "A P I",
    "CLI": "C L I",
    "TUI": "T U I",
    "GUI": "G U I",
    "LLM": "L L M",
    "SQLite": "S Q Lite",
    "Ollama": "Olama",
    "OpenAI": "Open A I",
    "Docker": "Docker",
    "Podman": "Podman",
    "systemd": "sístem D",
    "stdout": "standard out",
    "stderr": "standard error",
    "JSON": "J S O N",
    "YAML": "Y A M L",
    "TOML": "T O M L",
    "README": "read me",
    "Makefile": "make file",
    "GitHub": "Git Hub",
    "Sentry": "Sêntri",
}

_EXT_PRONUNCIATION = {
    "py": "Python",
    "rs": "Rust",
    "toml": "T O M L",
    "md": "Markdown",
    "json": "J S O N",
    "yaml": "Y A M L",
    "yml": "Y A M L",
    "lock": "lock file",
    "env": "env file",
    "ini": "I N I",
    "cfg": "config",
    "conf": "config",
    "html": "H T M L",
    "css": "C S S",
    "js": "JavaScript",
    "jsx": "J S X",
    "ts": "TypeScript",
    "tsx": "T S X",
    "go": "Go",
    "sql": "S Q L",
    "txt": "texto",
    "sh": "shell",
    "deb": "Debian package",
    "service": "serviço systemd",
    "sqlite3": "SQLite",
    "log": "log",
    "onnx": "O N N X",
    "bin": "binary",
    "wav": "WAV",
    "mp3": "MP3",
}

_IDENTIFIER_ACRONYMS = {
    "api": "A P I",
    "asr": "A S R",
    "ci": "C I",
    "cli": "C L I",
    "cpu": "C P U",
    "css": "C S S",
    "db": "D B",
    "gui": "G U I",
    "html": "H T M L",
    "http": "H T T P",
    "https": "H T T P S",
    "id": "I D",
    "json": "J S O N",
    "llm": "L L M",
    "ram": "R A M",
    "sql": "S Q L",
    "sqlx": "S Q L X",
    "tts": "T T S",
    "ui": "U I",
    "url": "U R L",
    "uuid": "U U I D",
    "yaml": "Y A M L",
}


def speech_text(value: str) -> str:
    """Converts Markdown-ish assistant output into natural text for TTS."""
    text = str(value or "")
    if not text.strip():
        return ""

    text = _FENCE_RE.sub(
        lambda m: f"\nTrecho de código omitido para leitura por voz.\n", text
    )
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(lambda m: _speak_code_token(m.group(1)), text)
    text = _PATH_RE.sub(lambda m: _speak_path(m.group(0)), text)
    text = _FILE_RE.sub(lambda m: _speak_file(m.group(0)), text)

    for term, spoken in sorted(
        _TERM_PRONUNCIATION.items(), key=lambda item: -len(item[0])
    ):
        text = re.sub(rf"\b{re.escape(term)}\b", spoken, text, flags=re.IGNORECASE)

    text = _speak_model_names(text)

    replacements = {
        "→": " para ",
        "=>": " para ",
        "->": " para ",
        "—": ", ",
        "–": ", ",
        "|": ", ",
        "/": " ou ",
        "\\": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"\*([^*]+)\*", r"\1", line)
        line = re.sub(r"__([^_]+)__", r"\1", line)
        line = re.sub(r"_([^_]+)_", r"\1", line)
        line = re.sub(r"[#*_`~<>{}\[\]]+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    text = ". ".join(lines)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([.!?]){2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _speak_code_token(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if "/" in token or "\\" in token:
        return _speak_path(token)
    if _FILE_RE.fullmatch(token):
        return _speak_file(token)
    return _speak_identifier(token)


def _speak_path(value: str) -> str:
    path = str(value or "").strip()
    if not path:
        return ""
    parts = [part for part in re.split(r"[\\/]+", path) if part and part != "."]
    if not parts:
        return path
    spoken_parts = [
        _speak_file(part) if "." in part else _speak_identifier(part)
        for part in parts[-3:]
    ]
    prefix = "caminho "
    if len(parts) > 3:
        prefix += "terminando em "
    return prefix + ", ".join(spoken_parts)


def _speak_file(value: str) -> str:
    name = str(value or "").strip()
    if "." not in name:
        return _speak_identifier(name)
    stem, ext = name.rsplit(".", 1)
    stem = _speak_identifier(_TERM_PRONUNCIATION.get(stem, stem))
    spoken_ext = _EXT_PRONUNCIATION.get(ext.lower(), ext)
    return f"arquivo {stem}, ponto {spoken_ext}"


def _speak_identifier(value: str) -> str:
    identifier = str(value or "").strip()
    if not identifier:
        return ""

    exact = _TERM_PRONUNCIATION.get(identifier)
    if exact:
        return exact

    identifier = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", identifier)
    identifier = identifier.replace("_", " ").replace("-", " ")
    words = []
    for part in identifier.split():
        lower = part.lower()
        if lower in _IDENTIFIER_ACRONYMS:
            words.append(_IDENTIFIER_ACRONYMS[lower])
        else:
            words.append(_TERM_PRONUNCIATION.get(part, part))
    return " ".join(words)


def _speak_model_names(text: str) -> str:
    text = re.sub(
        r"\bqwen(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)b\b", r"Qwen \1, \2 B", text, flags=re.I
    )
    text = re.sub(
        r"\bllama(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)b\b",
        r"Lhama \1, \2 B",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\bgemma(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)b-cloud\b",
        r"Guéma \1, \2 B cloud",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bgpt-(\d+(?:\.\d+)?)\b", r"G P T \1", text, flags=re.I)
    return text


def display_text(value: str) -> str:
    """Returns readable text without raw Markdown control signs."""
    text = str(value or "")
    if not text.strip():
        return ""
    text = _FENCE_RE.sub(lambda m: m.group(1).strip(), text)
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = text.replace("→", " para ").replace("=>", " para ").replace("->", " para ")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "• ", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"\*([^*]+)\*", r"\1", line)
        line = re.sub(r"__([^_]+)__", r"\1", line)
        line = re.sub(r"_([^_]+)_", r"\1", line)
        line = line.replace("`", "")
        line = re.sub(r"\s+", " ", line).strip()
        lines.append(line)
    return "\n".join(lines).strip()


def pango_markup(value: str) -> str:
    """Returns safe Pango markup for simple rich desktop labels."""
    text = str(value or "")
    if not text.strip():
        return ""
    placeholders: list[str] = []

    def bold(match: re.Match[str]) -> str:
        placeholders.append(_escape_markup(match.group(1)))
        return f"@@BOLD{len(placeholders) - 1}@@"

    text = re.sub(r"\*\*([^*]+)\*\*", bold, text)
    text = _escape_markup(display_text(text))
    for idx, content in enumerate(placeholders):
        text = text.replace(f"@@BOLD{idx}@@", f"<b>{content}</b>")
    return text


def _escape_markup(value: str) -> str:
    return (
        str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
