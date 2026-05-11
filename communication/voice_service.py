import os
import base64

from nexus_core.response_text import speech_text

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Configuração da voz do ZEUS
# Sugestão: pt-BR-AntonioNeural (Masculino, Profundo, Autoritário)
VOICE = "pt-BR-AntonioNeural"


class VoiceService:
    def __init__(self, output_dir="data/voice_temp"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    async def generate_speech_base64(self, text: str) -> str:
        """
        Gera o áudio a partir do texto e retorna em Base64 para envio via WebSocket.
        """
        if edge_tts is None:
            print("[VOICE SERVICE ERROR] edge-tts não está instalado.")
            return ""

        try:
            text = speech_text(text)
            if not text:
                return ""
            temp_file = os.path.join(self.output_dir, "response.mp3")
            communicate = edge_tts.Communicate(text, VOICE, rate="+5%", pitch="+0Hz")
            await communicate.save(temp_file)

            with open(temp_file, "rb") as f:
                audio_data = f.read()

            # Retorna como base64 para clientes locais tocarem.
            return base64.b64encode(audio_data).decode("utf-8")
        except Exception as e:
            print(f"[VOICE SERVICE ERROR] {e}")
            return ""

    async def generate_speech_wav(self, text: str) -> bytes:
        """
        Gera áudio em formato WAV (bytes).
        """
        base64_str = await self.generate_speech_base64(text)
        if not base64_str:
            return b""
        return base64.b64decode(base64_str)


voice_service = VoiceService()
