"""Voice output module: text-to-speech using edge-tts (free, Microsoft voices)."""
import asyncio
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Available German voices (edge-tts)
GERMAN_VOICES = [
    "de-DE-KatjaNeural",       # Female, standard
    "de-DE-ConradNeural",      # Male, standard
    "de-DE-AmalaNeural",       # Female, friendly
    "de-AT-IngridNeural",      # Austrian female
    "de-CH-LeniNeural",        # Swiss female
]

# Available English voices
ENGLISH_VOICES = [
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
]

ALL_VOICES = GERMAN_VOICES + ENGLISH_VOICES


class TTSEngine:
    """Text-to-speech engine using edge-tts."""

    def __init__(
        self,
        voice: str = "de-DE-KatjaNeural",
        rate: str = "+0%",
        volume: str = "+0%",
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._playing = False
        self._current_process = None

    async def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Synthesize text to an MP3 file.
        Returns path to the audio file, or None on failure.
        """
        try:
            import edge_tts

            if output_path is None:
                fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="a0_tts_")
                os.close(fd)

            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
            await communicate.save(output_path)
            logger.info(f"TTS saved to {output_path}")
            return output_path

        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return None
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    async def speak(self, text: str) -> bool:
        """
        Synthesize and play text immediately.
        Returns True if successful.
        """
        if not text.strip():
            return False

        # Truncate very long texts for TTS
        if len(text) > 1000:
            text = text[:1000] + "..."

        audio_path = await self.synthesize(text)
        if not audio_path:
            return False

        try:
            success = await self._play_audio(audio_path)
            return success
        finally:
            # Clean up temp file
            if os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass

    async def _play_audio(self, audio_path: str) -> bool:
        """Play an audio file using pygame or system player."""
        # Try pygame first
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            self._playing = True

            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            self._playing = False
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pygame playback failed: {e}")

        # Fallback: system player
        return await self._play_system(audio_path)

    async def _play_system(self, audio_path: str) -> bool:
        """Play audio using the system's default player."""
        import sys
        import subprocess

        try:
            if sys.platform == "win32":
                cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{audio_path}').PlaySync()"]
            elif sys.platform == "darwin":
                cmd = ["afplay", audio_path]
            else:
                # Linux: try multiple players
                for player in ["mpg123", "mpg321", "ffplay", "aplay"]:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            player, audio_path,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await proc.wait()
                        return True
                    except FileNotFoundError:
                        continue
                logger.warning("No audio player found on Linux")
                return False

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return True
        except Exception as e:
            logger.error(f"System audio playback failed: {e}")
            return False

    def stop(self):
        """Stop current playback."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self._playing = False

    def set_voice(self, voice: str):
        """Change the TTS voice."""
        self.voice = voice

    def set_rate(self, rate_percent: int):
        """
        Set speech rate as percentage change.
        rate_percent=0 means normal speed, +20 means 20% faster, -20 means 20% slower.
        """
        if rate_percent >= 0:
            self.rate = f"+{rate_percent}%"
        else:
            self.rate = f"{rate_percent}%"


# Global TTS instance
_tts_engine: Optional[TTSEngine] = None


def get_tts_engine(voice: str = "de-DE-KatjaNeural") -> TTSEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine(voice=voice)
    return _tts_engine
