"""Voice input module: records audio from microphone and transcribes via multiple backends.

Transcription backends (tried in order):
1. faster-whisper (local, offline) - if installed
2. SpeechRecognition + Google free API (online, no key needed)
3. macOS native speech recognition (offline, macOS only)
"""
import asyncio
import logging
import os
import sys
import tempfile
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceRecorder:
    """
    Records audio from the microphone using sounddevice.
    Supports push-to-talk (start/stop).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self._recording = False
        self._frames: list = []
        self._stream = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start recording. Returns True if successful."""
        try:
            import sounddevice as sd  # noqa: F811

            self._frames = []
            self._recording = True

            def callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                if self._recording:
                    with self._lock:
                        self._frames.append(indata.copy())

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=callback,
            )
            self._stream.start()
            logger.info("Recording started")
            return True
        except ImportError:
            logger.error("sounddevice not installed. Run: pip install sounddevice")
            return False
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    def stop(self) -> Optional[str]:
        """
        Stop recording and save to a WAV file.
        Returns path to the saved audio file, or None on failure.
        """
        try:
            import numpy as np
            import soundfile as sf

            self._recording = False
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            with self._lock:
                frames = list(self._frames)

            if not frames:
                logger.warning("No audio recorded")
                return None

            audio_data = np.concatenate(frames, axis=0)
            duration = len(audio_data) / self.sample_rate

            # Skip very short recordings (< 0.3s = likely just a click)
            if duration < 0.3:
                logger.warning(f"Recording too short ({duration:.1f}s), skipping")
                return None

            fd, path = tempfile.mkstemp(suffix=".wav", prefix="a0_voice_")
            os.close(fd)

            sf.write(path, audio_data, self.sample_rate)
            logger.info(f"Audio saved to {path} ({duration:.1f}s)")
            return path

        except ImportError:
            logger.error("soundfile not installed. Run: pip install soundfile")
            return None
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return None

    @property
    def is_recording(self) -> bool:
        return self._recording


# ---------------------------------------------------------------------------
# Transcription backends
# ---------------------------------------------------------------------------

class WhisperTranscriber:
    """Transcribes audio using faster-whisper (local, offline)."""

    def __init__(self, model_size: str = "base", language: str = "de"):
        self.model_size = model_size
        self.language = language
        self._model = None
        self._model_lock = threading.Lock()

    @staticmethod
    def is_available() -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from faster_whisper import WhisperModel
                    logger.info(f"Loading Whisper model: {self.model_size}")
                    self._model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    logger.info("Whisper model loaded")
        return self._model

    def transcribe(self, audio_path: str) -> str:
        model = self._load_model()
        if model is None:
            return ""
        try:
            segments, info = model.transcribe(
                audio_path,
                language=self.language if self.language else None,
                beam_size=5,
            )
            text = " ".join(seg.text.strip() for seg in segments)
            logger.info(f"[faster-whisper] Transcribed: {text[:100]}")
            return text.strip()
        except Exception as e:
            logger.error(f"[faster-whisper] Transcription failed: {e}")
            return ""


class SpeechRecognitionTranscriber:
    """Transcribes audio using the SpeechRecognition library (Google free API)."""

    def __init__(self, language: str = "de"):
        # Map short codes to full locale codes for Google API
        lang_map = {
            "de": "de-DE", "en": "en-US", "fr": "fr-FR",
            "es": "es-ES", "it": "it-IT", "pt": "pt-BR",
            "nl": "nl-NL", "ja": "ja-JP", "zh": "zh-CN",
            "ko": "ko-KR", "ru": "ru-RU", "pl": "pl-PL",
        }
        self.language = lang_map.get(language, language)

    @staticmethod
    def is_available() -> bool:
        try:
            import speech_recognition  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe(self, audio_path: str) -> str:
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=self.language)
            logger.info(f"[SpeechRecognition/Google] Transcribed: {text[:100]}")
            return text.strip()
        except ImportError:
            logger.error("SpeechRecognition not installed. Run: pip install SpeechRecognition")
            return ""
        except Exception as e:
            logger.error(f"[SpeechRecognition/Google] Transcription failed: {e}")
            return ""


class MacOSTranscriber:
    """Transcribes audio using macOS native NSSpeechRecognizer (offline)."""

    def __init__(self, language: str = "de"):
        self.language = language

    @staticmethod
    def is_available() -> bool:
        if sys.platform != "darwin":
            return False
        try:
            import subprocess
            # Check if 'say' command exists (basic macOS check)
            result = subprocess.run(["which", "say"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    def transcribe(self, audio_path: str) -> str:
        """Use macOS 'afplay' won't help - this is a placeholder.
        Real macOS STT requires SFSpeechRecognizer which needs Swift/ObjC bridge.
        For now, this backend is not functional - use SpeechRecognition instead.
        """
        return ""


# ---------------------------------------------------------------------------
# Multi-backend transcriber
# ---------------------------------------------------------------------------

class MultiTranscriber:
    """
    Tries multiple transcription backends in order:
    1. faster-whisper (local, offline)
    2. SpeechRecognition + Google (online, free, no key)
    """

    def __init__(self, model_size: str = "base", language: str = "de"):
        self.model_size = model_size
        self.language = language
        self._backends = []
        self._init_backends()

    def _init_backends(self):
        """Initialize available backends in priority order."""
        # 1. faster-whisper (best quality, offline)
        if WhisperTranscriber.is_available():
            self._backends.append(
                ("faster-whisper", WhisperTranscriber(self.model_size, self.language))
            )
            logger.info("Transcription backend: faster-whisper (local) ✓")

        # 2. SpeechRecognition + Google (easy, online)
        if SpeechRecognitionTranscriber.is_available():
            self._backends.append(
                ("google-speech", SpeechRecognitionTranscriber(self.language))
            )
            logger.info("Transcription backend: SpeechRecognition/Google ✓")

        if not self._backends:
            logger.error(
                "No transcription backend available! Install one of:\n"
                "  pip install SpeechRecognition   (easiest, uses Google free API)\n"
                "  pip install faster-whisper       (offline, needs torch)"
            )

    def transcribe(self, audio_path: str) -> str:
        """Try each backend until one succeeds."""
        if not self._backends:
            logger.error("No transcription backend available")
            return ""

        for name, backend in self._backends:
            try:
                logger.info(f"Trying transcription backend: {name}")
                text = backend.transcribe(audio_path)
                if text:
                    return text
                logger.warning(f"Backend {name} returned empty result")
            except Exception as e:
                logger.warning(f"Backend {name} failed: {e}")
                continue

        logger.error("All transcription backends failed")
        return ""

    async def transcribe_async(self, audio_path: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe, audio_path)

    def get_available_backends(self) -> list[str]:
        """Return list of available backend names."""
        return [name for name, _ in self._backends]


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

_recorder: Optional[VoiceRecorder] = None
_transcriber: Optional[MultiTranscriber] = None


def get_recorder() -> VoiceRecorder:
    global _recorder
    if _recorder is None:
        _recorder = VoiceRecorder()
    return _recorder


def get_transcriber(model_size: str = "base", language: str = "de") -> MultiTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = MultiTranscriber(model_size=model_size, language=language)
    return _transcriber
