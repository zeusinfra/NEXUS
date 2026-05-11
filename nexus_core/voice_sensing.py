from __future__ import annotations

import asyncio
import threading
import tempfile
import os
import sys
import subprocess
import time
import ctypes
import shutil
import re
import unicodedata
from nexus_core.response_text import speech_text

try:
    import speech_recognition as sr
except Exception:
    sr = None

if sr is None:
    # Mock para evitar crashes em ambiente CI sem dependências de áudio
    class _Mock:
        class AudioData:
            pass

        class WaitTimeoutError(Exception):
            pass

        class Recognizer:
            def __init__(self):
                self.dynamic_energy_threshold = True

            def listen(self, *a, **k):
                pass

        class Microphone:
            @staticmethod
            def list_microphone_names():
                return []

    sr = _Mock()

try:
    import edge_tts
except Exception:
    edge_tts = None

if edge_tts is None:

    class _Mock:
        class Communicate:
            def __init__(self, *a, **k):
                pass

            async def save(self, *a, **k):
                pass

    edge_tts = _Mock()


def _suppress_alsa_errors():
    """Suprime mensagens de erro ALSA/JACK que poluem o terminal."""
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        c_error_handler = ctypes.CFUNCTYPE(
            None,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
        )

        def _null_handler(filename, line, function, err, fmt):
            pass

        asound.snd_lib_error_set_handler(c_error_handler(_null_handler))
    except Exception:
        pass


def _configure_stdout_encoding() -> None:
    # Força encoding UTF-8 para evitar erros com acentos do Português.
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if getattr(sys.stdout, "encoding", None) == "utf-8":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class VoiceSensing:
    """Módulo de Escuta Ativa 100% Local para o NEXUS.
    Detecta silêncio (VAD), converte áudio localmente via Whisper e toca via Edge-TTS.
    """

    def __init__(self, broadcast_callback=None, wake_word="nexus", llm_callback=None):
        _configure_stdout_encoding()
        _suppress_alsa_errors()
        self.available = sr is not None and edge_tts is not None
        self.recognizer = sr.Recognizer() if sr is not None else None
        self.wake_word = wake_word.lower()
        self.llm_callback = llm_callback
        self.broadcast = broadcast_callback

        self.is_listening = False
        self.is_speaking = False
        self.thread = None
        self._loop = None
        self._whisper_lock = threading.Lock()
        self._ignore_audio_until = 0.0
        self._armed_until = 0.0
        aliases_env = os.getenv("NEXUS_WAKE_ALIASES", "").strip()
        aliases = [self.wake_word]
        self.wake_word_required = os.getenv(
            "NEXUS_WAKE_WORD_REQUIRED", "1"
        ).strip().lower() in {"1", "true", "yes", "on"}
        if aliases_env:
            aliases.extend(
                [part.strip() for part in aliases_env.split(",") if part.strip()]
            )
        else:
            # Default PT-BR: Whisper às vezes entende "Zeus" como "Deus".
            if self._normalize_text(self.wake_word) == "nexus":
                aliases.append("nexus")
        self._wake_aliases = [a for a in aliases if a]
        self._wake_re = self._build_wake_regex(self._wake_aliases)

        # Ajustes de sensibilidade (VAD)
        if self.recognizer is not None:
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            self.recognizer.energy_threshold = 600
        self.whisper_model = None

    @staticmethod
    def _normalize_text(value: str) -> str:
        txt = unicodedata.normalize("NFD", value)
        txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
        txt = txt.lower()
        txt = re.sub(r"[^a-z0-9\s]+", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    @classmethod
    def _build_wake_regex(cls, wake_aliases: list[str]) -> re.Pattern:
        parts = []
        for alias in wake_aliases:
            w = cls._normalize_text(alias)
            if w:
                parts.append(re.escape(w))
        if not parts:
            parts = [re.escape(cls._normalize_text("nexus"))]
        # \b evita disparar no meio de palavras.
        return re.compile(rf"\b(?:{'|'.join(parts)})\b", re.IGNORECASE)

    def _strip_wake_word(self, text: str) -> str:
        normalized = self._normalize_text(text)
        normalized = self._wake_re.sub("", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def arm(self, seconds=10):
        """Ativa a escuta sem wake word por um período determinado."""
        self._armed_until = time.time() + seconds
        print(f"[NEXUS LOCAL] Escuta armada por {seconds}s.")

    def _ensure_whisper_loaded(self):
        if self.whisper_model is not None:
            return
        with self._whisper_lock:
            if self.whisper_model is not None:
                return
            try:
                from faster_whisper import WhisperModel
            except Exception as exc:
                raise RuntimeError(
                    "Voice transcription is unavailable. Install requirements/voice.txt "
                    "to enable faster-whisper."
                ) from exc
            print("[NEXUS LOCAL] Carregando modelo Faster-Whisper...")
            model_name = os.getenv("NEXUS_WHISPER_MODEL", "small").strip() or "small"
            self.whisper_model = WhisperModel(
                model_name, device="cpu", compute_type="int8"
            )
            print("[NEXUS LOCAL] Whisper pronto.")

    async def _send_status(self, text):
        if self.broadcast:
            await self.broadcast({"type": "HUD_STATUS", "text": text})

    async def _send_voice_state(self, stage: str, **extra):
        if not self.broadcast:
            return
        payload = {"type": "VOICE_STATE", "stage": stage}
        payload.update({k: v for k, v in extra.items() if v is not None})
        await self.broadcast(payload)

    def _listen_loop(self):
        """Loop síncrono de captura de áudio (roda em thread separada)."""
        if sr is None or self.recognizer is None:
            print(
                "[NEXUS LOCAL] Voice sensing unavailable: SpeechRecognition is not installed."
            )
            self.is_listening = False
            return
        if os.getenv("NEXUS_MIC_LIST", "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            try:
                names = sr.Microphone.list_microphone_names()
                print("[NEXUS LOCAL] Dispositivos de microfone:")
                for idx, name in enumerate(names):
                    print(f"  [{idx}] {name}")
            except Exception as e:
                print(f"[NEXUS LOCAL] ⚠️ Falha ao listar microfones: {e}")
        try:
            device_index = os.getenv("NEXUS_MIC_DEVICE_INDEX")
            mic_kwargs = {}
            mic_name = os.getenv("NEXUS_MIC_NAME", "").strip()
            if mic_name:
                try:
                    names = sr.Microphone.list_microphone_names()
                    match = None
                    needle = mic_name.lower()
                    for idx, name in enumerate(names):
                        if needle in str(name).lower():
                            match = idx
                            break
                    if match is None:
                        print(
                            f"[NEXUS LOCAL] ⚠️ NEXUS_MIC_NAME não encontrado: '{mic_name}'. Use NEXUS_MIC_LIST=1 para listar."
                        )
                    else:
                        mic_kwargs["device_index"] = match
                        print(
                            f"[NEXUS LOCAL] 🎙️ Microfone selecionado por nome: [{match}] {names[match]}"
                        )
                except Exception as e:
                    print(f"[NEXUS LOCAL] ⚠️ Falha ao selecionar microfone por nome: {e}")
            elif device_index is not None and str(device_index).strip() != "":
                try:
                    mic_kwargs["device_index"] = int(str(device_index).strip())
                except Exception:
                    print(
                        f"[NEXUS LOCAL] ⚠️ NEXUS_MIC_DEVICE_INDEX inválido: {device_index}"
                    )
            mic = sr.Microphone(**mic_kwargs)
        except Exception as e:
            print(f"[NEXUS LOCAL] ❌ Falha ao abrir microfone: {e}")
            print(
                "[NEXUS LOCAL] Verifique se há um dispositivo de áudio conectado (ex: DroidCam)."
            )
            self.is_listening = False
            return

        with mic as source:
            print("[NEXUS LOCAL] Calibrando microfone...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("[NEXUS LOCAL] Ouvindo...")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_voice_state("listening"), self._loop
                )

            while self.is_listening:
                if self.is_speaking:
                    # Pausa a escuta enquanto o NEXUS está falando
                    time.sleep(0.2)
                    continue
                if time.time() < self._ignore_audio_until:
                    time.sleep(0.1)
                    continue

                try:
                    # Captura o áudio até detectar silêncio (pause_threshold)
                    try:
                        phrase_limit = float(os.getenv("NEXUS_PHRASE_TIME_LIMIT", "6"))
                    except Exception:
                        phrase_limit = 6.0
                    audio_data = self.recognizer.listen(
                        source, timeout=2, phrase_time_limit=max(1.0, phrase_limit)
                    )

                    if self.is_speaking:
                        continue  # Ignora áudio captado enquanto falava

                    self._process_audio(audio_data)

                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"[NEXUS LOCAL] Erro de captura: {e}")

    def _process_audio(self, audio_data: sr.AudioData):
        if self._loop and self.broadcast:
            asyncio.run_coroutine_threadsafe(
                self._send_status("Transcrevendo audio..."), self._loop
            )
            asyncio.run_coroutine_threadsafe(
                self._send_voice_state("transcribing"), self._loop
            )

        tmp_path = None
        try:
            self._ensure_whisper_loaded()
            # Salva o áudio em disco para o Whisper ler (prefixo ASCII-safe)
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="nexus_asr_"
            ) as tmp:
                tmp.write(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
                tmp_path = tmp.name

            vad = os.getenv("NEXUS_WHISPER_VAD", "1").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            segments, info = self.whisper_model.transcribe(
                tmp_path,
                language="pt",
                beam_size=1,
                vad_filter=vad,
            )

            # Coleta texto com proteção de encoding
            text_parts = []
            for seg in segments:
                t = seg.text
                if isinstance(t, bytes):
                    t = t.decode("utf-8", errors="replace")
                if t and t.strip():
                    text_parts.append(t.strip())

            text = " ".join(text_parts).strip()

            if text:
                normalized = self._normalize_text(text)
                now = time.time()

                armed = now < self._armed_until
                woke = bool(self._wake_re.search(normalized))

                # Só processa comando se:
                # - contém wake word (ex: "Zeus, ..."), OU
                # - foi "armado" por um wake anterior (dizer só "Zeus" e depois falar o comando).
                # - OU se o wake word NÃO for obrigatório.
                if not (woke or armed or not self.wake_word_required):
                    if os.getenv("NEXUS_VOICE_DEBUG", "0").strip().lower() in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }:
                        try:
                            print(f"[VOICE DEBUG] (sem wake) {text}")
                        except UnicodeEncodeError:
                            print("[VOICE DEBUG] (sem wake) (encoding issue)")
                    return

                command = self._strip_wake_word(text) if woke else normalized
                if os.getenv("NEXUS_VOICE_DEBUG", "0").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }:
                    try:
                        print(
                            f"[VOICE DEBUG] wake={1 if woke else 0} armed={1 if armed else 0} command='{command}' raw='{text}'"
                        )
                    except UnicodeEncodeError:
                        print("[VOICE DEBUG] wake=1 (encoding issue)")

                # Print com encoding seguro
                try:
                    print(f"[USER] {text}")
                except UnicodeEncodeError:
                    print("[USER] (fala com caracteres especiais)")

                # Wake word sozinho -> ack local (não gasta LLM)
                if woke and not command:
                    try:
                        arm_sec = float(os.getenv("NEXUS_WAKE_ARM_SEC", "8"))
                    except Exception:
                        arm_sec = 8.0
                    self._armed_until = time.time() + max(0.0, arm_sec)
                    if self._loop:
                        if self.broadcast:
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast({"type": "CHAT_USER", "message": text}),
                                self._loop,
                            )
                        asyncio.run_coroutine_threadsafe(
                            self.speak("Pode falar."), self._loop
                        )
                    return

                # Se consumiu um comando no modo armado, desarma.
                if armed and not woke:
                    self._armed_until = 0.0

                # Envia para o LLM (texto original)
                if self.llm_callback and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self.llm_callback(text), self._loop
                    )

        except Exception as e:
            try:
                print(f"[NEXUS LOCAL] Erro no Whisper: {e}")
            except UnicodeEncodeError:
                print("[NEXUS LOCAL] Erro no Whisper (encoding issue)")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    async def speak(self, text: str):
        """Sintetiza e toca o áudio, travando o microfone enquanto fala."""
        if not text or not text.strip():
            return
        spoken_text = speech_text(text)
        if not spoken_text:
            return

        try:
            print(f"[NEXUS] {text}")
        except UnicodeEncodeError:
            print("[NEXUS] (resposta com caracteres especiais)")

        if self.broadcast:
            await self.broadcast({"type": "CHAT_AI", "message": text})
            await self._send_status("Sintetizando voz...")
            await self._send_voice_state("speaking", text_preview=spoken_text[:80])

        self.is_speaking = True
        try:
            tmp_path = None
            try:
                VOICE = "pt-BR-AntonioNeural"
                if edge_tts is None:
                    raise RuntimeError("edge-tts is not installed")
                communicate = edge_tts.Communicate(
                    spoken_text, VOICE, rate="+5%", pitch="-2Hz"
                )

                with tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False, prefix="nexus_tts_"
                ) as tmp:
                    tmp_path = tmp.name

                tts_timeout = float(os.getenv("NEXUS_TTS_TIMEOUT_SEC", "12"))
                await asyncio.wait_for(communicate.save(tmp_path), timeout=tts_timeout)

                if self.broadcast:
                    await self._send_status("Falando...")

                play_timeout = float(os.getenv("NEXUS_AUDIO_PLAY_TIMEOUT_SEC", "45"))

                # Tocar MP3 diretamente para evitar delay de conversão
                proc = await asyncio.create_subprocess_exec(
                    "ffplay",
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "error",
                    tmp_path,
                    stdout=subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _out, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=play_timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise RuntimeError(f"ffplay travou (timeout={play_timeout}s)")
                rc = proc.returncode
                if rc != 0:
                    err = (stderr or b"").decode(errors="ignore").strip()
                    raise RuntimeError(
                        f"ffplay falhou (rc={rc}){': ' + err if err else ''}"
                    )
            except Exception as edge_err:
                # Fallback offline via Speech Dispatcher (spd-say), se disponível.
                spd = shutil.which("spd-say")
                if not spd:
                    raise edge_err

                if self.broadcast:
                    await self._send_status("Falando (fallback local)...")

                speak_timeout = float(os.getenv("NEXUS_SPD_SAY_TIMEOUT_SEC", "20"))
                proc = await asyncio.create_subprocess_exec(
                    spd,
                    "-w",
                    "-l",
                    "pt",
                    spoken_text,
                    stdout=subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    # Evita travar indefinidamente em setups sem speech-dispatcher/voz.
                    _out, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=speak_timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise RuntimeError(
                        f"spd-say travou (timeout={speak_timeout}s)"
                    ) from edge_err
                rc = proc.returncode
                if rc != 0:
                    err = stderr.decode(errors="ignore").strip()
                    raise RuntimeError(
                        f"spd-say falhou (rc={rc}){': ' + err if err else ''}"
                    ) from edge_err
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[NEXUS LOCAL] Erro de TTS: {e}")
        finally:
            self.is_speaking = False
            # pequena janela para evitar eco do próprio TTS após o fim do playback
            try:
                post = float(os.getenv("NEXUS_POST_SPEAK_IGNORE_SEC", "0.9"))
            except Exception:
                post = 0.9
            self._ignore_audio_until = max(
                self._ignore_audio_until, time.time() + max(0.0, post)
            )
            if self.broadcast:
                await self._send_status("Aguardando atividade neural...")
                await self._send_voice_state(
                    "listening" if self.is_listening else "idle"
                )

    async def run(self):
        """Inicia o loop assíncrono do módulo."""
        self._loop = asyncio.get_event_loop()
        if sr is None:
            await self._send_status(
                "Modulo de voz indisponivel: SpeechRecognition ausente."
            )
            return
        await asyncio.to_thread(self._ensure_whisper_loaded)

        if not self.is_listening:
            self.is_listening = True
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()

        await self._send_status("Modulo de voz local (Whisper) online.")

        while self.is_listening:
            await asyncio.sleep(1)

    def stop(self):
        self.is_listening = False
        if self.thread:
            self.thread.join(timeout=2)
