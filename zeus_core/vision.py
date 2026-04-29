from __future__ import annotations

import base64
import datetime as _dt
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from zeus_core.tools import ToolError
from zeus_core.core_system import call_cloud_llm


def _project_root() -> Path:
    env_root = os.getenv("ZEUS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def capture_screen(*, save_dir: str = "scratch/screens") -> dict:
    try:
        import mss  # type: ignore
    except Exception as e:
        raise ToolError("Dependência ausente: instale 'mss' para captura de tela.") from e

    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        raise ToolError("Dependência ausente: instale 'pillow' para salvar PNG.") from e

    root = _project_root()
    out_dir = (root / save_dir).resolve()
    try:
        out_dir.relative_to(root)
    except Exception as e:
        raise ToolError("save_dir inválido (fora do projeto).") from e

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"screen-{ts}.png"

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            img.save(out_path, format="PNG", optimize=True)
    except Exception as e:
        raise ToolError(
            "Não foi possível capturar a tela neste ambiente (display indisponível). "
            "Se estiver rodando em modo headless/servidor, use captura client-side pelo navegador."
        ) from e

    return {
        "path": str(out_path),
        "width": int(img.size[0]),
        "height": int(img.size[1]),
    }


def ocr_image(path: str, *, lang: str = "por") -> dict:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise ToolError("Arquivo de imagem não encontrado para OCR.")

    # OCR opcional via tesseract CLI (se existir no sistema)
    if not shutil_which("tesseract"):
        raise ToolError("OCR indisponível: tesseract não encontrado no sistema.")

    with tempfile.TemporaryDirectory() as td:
        out_base = Path(td) / "out"
        proc = subprocess.run(
            ["tesseract", str(p), str(out_base), "-l", lang],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            raise ToolError(f"OCR falhou: {((proc.stderr or proc.stdout) or '')[:200]}")
        txt_path = Path(f"{out_base}.txt")
        text = txt_path.read_text(encoding="utf-8", errors="replace") if txt_path.exists() else ""
        return {"text": text[:50_000]}


def analyze_image_with_llm(path: str, *, question: str) -> dict:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise ToolError("Arquivo de imagem não encontrado para análise.")
    q = (question or "").strip()
    if not q:
        raise ToolError("question/text é obrigatório para análise por LLM.")

    img = image_to_base64(str(p), max_bytes=450_000)
    if img.get("truncated"):
        raise ToolError("Imagem grande demais para enviar ao modelo (truncada).")

    system = (
        "Você é o módulo de visão do ZEUS. Responda em PT-BR.\n"
        "Analise a imagem fornecida e responda à pergunta com precisão.\n"
        "Se não der para ter certeza, diga o que você consegue inferir e o que falta."
    )
    user_content = [
        {"type": "text", "text": q},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img['b64']}"},
        },
    ]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    answer = call_cloud_llm(messages)
    return {"answer": answer}


def analyze_with_ocr_fallback(path: str, *, question: str, ocr_lang: str = "por") -> dict:
    """
    Fallback robusto: tenta OCR local e pede para a LLM responder usando o texto extraído.
    """
    q = (question or "").strip()
    if not q:
        raise ToolError("question/text é obrigatório para análise.")

    ocr = ocr_image(path, lang=ocr_lang)
    ocr_text = (ocr.get("text") or "").strip()
    if not ocr_text:
        raise ToolError("OCR não retornou texto.")

    system = (
        "Você é o módulo de visão do ZEUS (modo OCR). Responda em PT-BR.\n"
        "Você NÃO viu a imagem: use apenas o texto OCR como fonte.\n"
        "Se o OCR parecer incompleto, deixe isso claro."
    )
    user = f"Pergunta: {q}\n\nOCR:\n{ocr_text}"
    answer = call_cloud_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return {"ocr": ocr, "answer": answer}


def image_to_base64(path: str, *, max_bytes: int = 300_000) -> dict:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise ToolError("Arquivo de imagem não encontrado.")
    data = p.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    b64 = base64.b64encode(data).decode("ascii")
    return {"b64": b64, "truncated": truncated, "bytes": len(data)}


def shutil_which(cmd: str) -> Optional[str]:
    try:
        import shutil

        return shutil.which(cmd)
    except Exception:
        return None


def is_tesseract_available() -> bool:
    return bool(shutil_which("tesseract"))
