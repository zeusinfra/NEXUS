import os
import base64
import io
import asyncio
import requests
from nexus_core.response_text import speech_text

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

# Configurações de Voz
KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
VOICE_NAME = "pm_alex" # Português Masculino (Alex)
LANG_CODE = "pt-br"    # Tentando código padrão para espeak

class VoiceService:
    def __init__(self, model_dir="models/tts"):
        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
        self.voices_path = os.path.join(model_dir, "voices-v1.0.bin")
        self.kokoro = None
        
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)

    def _ensure_models(self):
        """Garante que os modelos do Kokoro existam localmente."""
        if os.path.exists(self.model_path) and os.path.exists(self.voices_path):
            return True
        
        print("🧠 Modelos de voz (Kokoro) não encontrados. Iniciando download...")
        try:
            for url, path in [(KOKORO_MODEL_URL, self.model_path), (KOKORO_VOICES_URL, self.voices_path)]:
                if not os.path.exists(path):
                    print(f"📥 Baixando {os.path.basename(path)}...")
                    resp = requests.get(url, stream=True, timeout=60)
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
            print("✅ Modelos de voz baixados com sucesso.")
            return True
        except Exception as e:
            print(f"❌ Erro ao baixar modelos de voz: {e}")
            return False

    def _get_kokoro(self):
        if self.kokoro is None and Kokoro is not None:
            if self._ensure_models():
                try:
                    self.kokoro = Kokoro(self.model_path, self.voices_path)
                except Exception as e:
                    print(f"❌ Erro ao carregar Kokoro: {e}")
        return self.kokoro

    async def generate_speech_base64(self, text: str) -> str:
        """
        Gera o áudio usando Kokoro (Local) e retorna em Base64.
        """
        text = speech_text(text)
        if not text:
            return ""

        kokoro = self._get_kokoro()
        if kokoro is None or sf is None:
            print("[VOICE SERVICE] Kokoro ou soundfile não disponíveis. Verifique dependências.")
            return ""

        try:
            # Geração síncrona do Kokoro (é rápida, mas vamos rodar em thread para não travar o loop)
            loop = asyncio.get_event_loop()
            samples, sample_rate = await loop.run_in_executor(
                None, 
                lambda: kokoro.create(text, voice=VOICE_NAME, speed=1.0, lang=LANG_CODE)
            )

            # Converter para WAV em memória
            buffer = io.BytesIO()
            sf.write(buffer, samples, sample_rate, format='WAV')
            buffer.seek(0)
            
            return base64.b64encode(buffer.read()).decode("utf-8")
        except Exception as e:
            print(f"[VOICE SERVICE ERROR] {e}")
            return ""

    async def generate_speech_wav(self, text: str) -> bytes:
        """Gera áudio em formato WAV (bytes)."""
        base64_str = await self.generate_speech_base64(text)
        if not base64_str:
            return b""
        return base64.b64decode(base64_str)

voice_service = VoiceService()
