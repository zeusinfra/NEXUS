from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional
import threading

from nexus_core.tools import ToolError


def _which(cmd: str) -> Optional[str]:
    try:
        import shutil

        return shutil.which(cmd)
    except Exception:
        return None


_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _get_whisper_model(model_name: str, *, device: str, compute_type: str):
    """
    Reusa o WhisperModel entre requests para evitar picos de RAM/CPU.
    Cache por (model_name, device, compute_type).
    """
    key = (model_name, device, compute_type)
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            raise ToolError(
                "Dependência ausente: instale 'faster-whisper' para ASR local."
            ) from e

        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        _MODEL_CACHE[key] = model
        return model


def transcribe_audio_bytes(
    data: bytes, *, mime: str = "audio/webm", language: str = "pt"
) -> dict:
    """
    Transcreve um clipe de áudio curto.
    Entrada típica: WebM/Opus do MediaRecorder no navegador.
    Requer ffmpeg para converter para WAV.
    Requer faster-whisper para transcrição local.
    """
    if not data:
        raise ToolError("Áudio vazio.")

    ffmpeg = _which("ffmpeg")
    if not ffmpeg:
        raise ToolError(
            "ffmpeg não encontrado. Instale ffmpeg para decodificar áudio do navegador."
        )

    model_name = os.getenv("NEXUS_ASR_MODEL", "small").strip()
    device = os.getenv("NEXUS_ASR_DEVICE", "cpu").strip()
    compute_type = os.getenv("NEXUS_ASR_COMPUTE_TYPE", "int8").strip()

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / ("audio.webm" if "webm" in (mime or "") else "audio.bin")
        src.write_bytes(data)
        wav = td_path / "audio.wav"

        # Converte para WAV mono 16k
        import subprocess

        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0 or not wav.exists():
            msg = (proc.stderr or proc.stdout or "")[:300]
            raise ToolError(f"Falha ao converter áudio (ffmpeg). {msg}")

        model = _get_whisper_model(model_name, device=device, compute_type=compute_type)
        segments, info = model.transcribe(str(wav), language=language, vad_filter=True)
        text_parts = []
        for seg in segments:
            if seg.text:
                text_parts.append(seg.text.strip())
        text = " ".join(text_parts).strip()

        return {
            "text": text,
            "language": getattr(info, "language", language),
            "duration": getattr(info, "duration", None),
            "model": model_name,
        }
