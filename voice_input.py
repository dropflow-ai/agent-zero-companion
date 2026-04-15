"""Voice input module: records audio from microphone and transcribes via Whisper."""
import asyncio
import logging
import os
import tempfile
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceRecorder:
    """
    Records audio from the microphone using sounddevice.
    Supports push-to-talk (start/stop) and silence detection.
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
            import sounddevice as sd
            import numpy as np

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

            fd, path = tempfile.mkstemp(suffix=".wav", prefix="a0_voice_")
            os.close(fd)

            sf.write(path, audio_data, self.sample_rate)
            logger.info(f"Audio saved to {path} ({len(audio_data)/self.sample_rate:.1f}s)")
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


class WhisperTranscriber:
    """
    Transcribes audio using faster-whisper (local) or
    falls back to Agent Zero's /api/transcribe endpoint.
    """

    def __init__(self, model_size: str = "base", language: str = "de"):
        self.model_size = model_size
        self.language = language
        self._model = None
        self._model_lock = threading.Lock()

    def _load_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        from faster_whisper import WhisperModel
                        logger.info(f"Loading Whisper model: {self.model_size}")
                        self._model = WhisperModel(
                            self.model_size,
                            device="cpu",
                            compute_type="int8",
                        )
                        logger.info("Whisper model loaded")
                    except ImportError:
                        logger.warning(
                            "faster-whisper not installed. "
                            "Run: pip install faster-whisper"
                        )
                        return None
        return self._model

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text. Returns empty string on failure."""
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
            logger.info(f"Transcribed: {text[:100]}..." if len(text) > 100 else f"Transcribed: {text}")
            return text.strip()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    async def transcribe_async(self, audio_path: str) -> str:
        """Async wrapper for transcription."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe, audio_path)


# Global instances
_recorder: Optional[VoiceRecorder] = None
_transcriber: Optional[WhisperTranscriber] = None


def get_recorder() -> VoiceRecorder:
    global _recorder
    if _recorder is None:
        _recorder = VoiceRecorder()
    return _recorder


def get_transcriber(model_size: str = "base", language: str = "de") -> WhisperTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber(model_size=model_size, language=language)
    return _transcriber
