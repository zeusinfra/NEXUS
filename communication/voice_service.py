import asyncio
import base64
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from nexus_core.response_text import speech_text

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]

KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)

DEFAULT_ENGINE = os.getenv("NEXUS_TTS_ENGINE", "auto").strip().lower()
DEFAULT_EDGE_VOICE = os.getenv("NEXUS_TTS_EDGE_VOICE", "pt-BR-AntonioNeural").strip()
DEFAULT_EDGE_RATE = os.getenv("NEXUS_TTS_EDGE_RATE", "+0%").strip()
DEFAULT_EDGE_VOLUME = os.getenv("NEXUS_TTS_EDGE_VOLUME", "+0%").strip()
DEFAULT_EDGE_PITCH = os.getenv("NEXUS_TTS_EDGE_PITCH", "+0Hz").strip()
DEFAULT_KOKORO_VOICE = os.getenv("NEXUS_KOKORO_VOICE", "pm_alex").strip()
DEFAULT_KOKORO_LANG = os.getenv("NEXUS_KOKORO_LANG", "pt-br").strip()
DEFAULT_PIPER_MODEL = os.getenv(
    "NEXUS_TTS_PIPER_MODEL",
    str(PROJECT_ROOT / "models" / "piper" / "pt_BR_maria_low.onnx"),
).strip()


def default_tts_model_dir() -> Path:
    explicit = os.getenv("NEXUS_TTS_MODEL_DIR")
    if explicit:
        return Path(explicit).expanduser()

    runtime_dir = os.getenv("NEXUS_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir).expanduser() / "models" / "tts"

    if PROJECT_ROOT == Path("/usr/lib/nexus"):
        state_home = Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
        )
        return state_home / "nexus" / "models" / "tts"

    return PROJECT_ROOT / "models" / "tts"


class VoiceService:
    def __init__(self, model_dir: str | None = None):
        self.model_dir = (
            Path(model_dir).expanduser() if model_dir else default_tts_model_dir()
        )
        if not self.model_dir.is_absolute():
            self.model_dir = PROJECT_ROOT / self.model_dir
        self.model_path = self.model_dir / "kokoro-v1.0.onnx"
        self.voices_path = self.model_dir / "voices-v1.0.bin"
        self.kokoro = None
        self.last_mime_type = "audio/wav"
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def _engine_order(self) -> list[str]:
        engine = DEFAULT_ENGINE or "auto"
        if engine in {"off", "none", "disabled"}:
            return []
        if engine in {"edge", "piper", "kokoro"}:
            return [engine]
        if engine in {"local", "offline"}:
            return ["piper", "kokoro"]
        return ["edge", "piper", "kokoro"]

    async def generate_speech_audio(self, text: str) -> tuple[bytes, str]:
        """Generate PT-BR speech audio and return raw bytes plus MIME type."""
        spoken = speech_text(text)
        if not spoken:
            return b"", "audio/wav"

        max_chars = int(os.getenv("NEXUS_TTS_MAX_CHARS", "1800") or "1800")
        spoken = spoken[:max_chars]
        errors: list[str] = []

        for engine in self._engine_order():
            try:
                if engine == "edge":
                    timeout = float(os.getenv("NEXUS_EDGE_TTS_TIMEOUT_SEC", "18") or "18")
                    audio, mime = await asyncio.wait_for(
                        self._generate_edge_audio(spoken), timeout=timeout
                    )
                elif engine == "piper":
                    audio, mime = await self._generate_piper_audio(spoken)
                elif engine == "kokoro":
                    audio, mime = await self._generate_kokoro_audio(spoken)
                else:
                    continue

                if audio:
                    self.last_mime_type = mime
                    return audio, mime
            except Exception as exc:
                errors.append(f"{engine}: {exc}")

        if errors:
            print("[VOICE SERVICE] TTS indisponivel: " + " | ".join(errors))
        return b"", "audio/wav"

    async def generate_speech_payload(self, text: str) -> dict[str, str]:
        audio, mime = await self.generate_speech_audio(text)
        if not audio:
            return {"audio": "", "audio_mime": ""}
        return {
            "audio": base64.b64encode(audio).decode("utf-8"),
            "audio_mime": mime,
        }

    async def generate_speech_base64(self, text: str) -> str:
        payload = await self.generate_speech_payload(text)
        return payload["audio"]

    async def generate_speech_wav(self, text: str) -> bytes:
        """Backward-compatible audio bytes helper.

        The returned bytes may be MP3 when the neural PT-BR engine is selected.
        Use generate_speech_audio when the caller needs the exact MIME type.
        """
        audio, _mime = await self.generate_speech_audio(text)
        return audio

    async def _generate_edge_audio(self, text: str) -> tuple[bytes, str]:
        if edge_tts is None:
            raise RuntimeError("edge-tts nao esta instalado")

        communicate = edge_tts.Communicate(
            text,
            voice=DEFAULT_EDGE_VOICE,
            rate=DEFAULT_EDGE_RATE,
            volume=DEFAULT_EDGE_VOLUME,
            pitch=DEFAULT_EDGE_PITCH,
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk.get("data") or b"")

        audio = b"".join(chunks)
        if not audio:
            raise RuntimeError("edge-tts nao retornou audio")
        return audio, "audio/mpeg"

    async def _generate_piper_audio(self, text: str) -> tuple[bytes, str]:
        piper_bin = shutil.which("piper") or shutil.which("piper-tts")
        if not piper_bin:
            raise RuntimeError("piper CLI nao encontrado")

        model_path = Path(DEFAULT_PIPER_MODEL).expanduser()
        if not model_path.is_absolute():
            model_path = PROJECT_ROOT / model_path
        if not model_path.exists():
            raise RuntimeError(f"modelo Piper nao encontrado: {model_path}")

        timeout = float(os.getenv("NEXUS_PIPER_TIMEOUT_SEC", "30") or "30")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._run_piper(piper_bin, model_path, text, timeout)
        )

    def _run_piper(
        self, piper_bin: str, model_path: Path, text: str, timeout: float
    ) -> tuple[bytes, str]:
        with tempfile.TemporaryDirectory(prefix="nexus_piper_") as tmpdir:
            out_path = Path(tmpdir) / "speech.wav"
            proc = subprocess.run(
                [
                    piper_bin,
                    "--model",
                    str(model_path),
                    "--output_file",
                    str(out_path),
                ],
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="ignore").strip()
                raise RuntimeError(stderr or f"piper rc={proc.returncode}")
            if not out_path.exists():
                raise RuntimeError("piper nao gerou arquivo WAV")
            return out_path.read_bytes(), "audio/wav"

    async def _generate_kokoro_audio(self, text: str) -> tuple[bytes, str]:
        kokoro = self._get_kokoro()
        if kokoro is None or sf is None:
            raise RuntimeError("Kokoro ou soundfile indisponivel")

        loop = asyncio.get_event_loop()
        samples, sample_rate = await loop.run_in_executor(
            None,
            lambda: kokoro.create(
                text,
                voice=DEFAULT_KOKORO_VOICE,
                speed=float(os.getenv("NEXUS_KOKORO_SPEED", "1.0") or "1.0"),
                lang=DEFAULT_KOKORO_LANG,
            ),
        )

        buffer = io.BytesIO()
        sf.write(buffer, samples, sample_rate, format="WAV")
        buffer.seek(0)
        return buffer.read(), "audio/wav"

    def _ensure_models(self) -> bool:
        """Guarantee Kokoro model files exist locally."""
        if self.model_path.exists() and self.voices_path.exists():
            return True

        print("[VOICE SERVICE] Modelos Kokoro ausentes. Baixando fallback local...")
        try:
            for url, path in [
                (KOKORO_MODEL_URL, self.model_path),
                (KOKORO_VOICES_URL, self.voices_path),
            ]:
                if path.exists():
                    continue
                print(f"[VOICE SERVICE] Baixando {path.name}...")
                resp = requests.get(url, stream=True, timeout=60)
                resp.raise_for_status()
                with path.open("wb") as handle:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)
            return True
        except Exception as exc:
            print(f"[VOICE SERVICE] Erro ao baixar modelos Kokoro: {exc}")
            return False

    def _get_kokoro(self):
        if self.kokoro is None and Kokoro is not None:
            if self._ensure_models():
                try:
                    self.kokoro = Kokoro(str(self.model_path), str(self.voices_path))
                except Exception as exc:
                    print(f"[VOICE SERVICE] Erro ao carregar Kokoro: {exc}")
        return self.kokoro


voice_service = VoiceService()
