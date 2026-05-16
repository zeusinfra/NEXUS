import html
import re


_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n?(.*?)```", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def speech_text(value: str) -> str:
    """Converts Markdown-ish assistant output into natural text for TTS."""
    text = str(value or "")
    if not text.strip():
        return ""

    text = _FENCE_RE.sub(lambda m: f"\nTrecho de código: {m.group(1).strip()}\n", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)

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



