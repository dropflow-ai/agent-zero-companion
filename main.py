"""Agent Zero Companion - Main entry point.

A cross-platform desktop companion that connects to Agent Zero via HTTP API.
Features:
- System tray icon
- Global configurable hotkey
- Floating overlay near cursor
- Screenshot attachment
- Voice input (Whisper STT)
- Voice output (edge-tts TTS)

Usage:
    python main.py
    python main.py --settings   # Open settings on startup
"""
import asyncio
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("a0-companion")


class AgentZeroCompanion:
    """
    Main application class that orchestrates all components:
    - Qt application + overlay UI
    - System tray
    - Global hotkey listener
    - Async event loop (in background thread)
    - Agent Zero HTTP client
    """

    def __init__(self):
        self._app = None
        self._overlay = None
        self._tray = None
        self._hotkey_manager = None
        self._client = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._settings_dialog = None

    def run(self, open_settings: bool = False):
        """Start the application. Blocks until quit."""
        # Import Qt here to allow headless testing
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt

        # Create Qt application
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setApplicationName("Agent Zero Companion")
        self._app.setApplicationVersion("1.0.0")
        self._app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        # Load config
        from config import config
        self._config = config

        # Initialize async event loop in background thread
        self._start_async_loop()

        # Initialize Agent Zero client
        self._init_client()

        # Build overlay
        self._init_overlay()

        # Start system tray
        self._init_tray()

        # Register global hotkey
        self._init_hotkey()

        # Open settings on first run or if requested
        if open_settings or not self._config.get("agent_zero_url"):
            self._show_settings()

        logger.info("Agent Zero Companion started")
        logger.info(f"Hotkey: {self._config.get('hotkey', '<ctrl>+<space>')}")
        logger.info(f"Agent Zero URL: {self._config.get('agent_zero_url')}")

        # Run Qt event loop (blocks)
        exit_code = self._app.exec()
        self._cleanup()
        return exit_code

    def _start_async_loop(self):
        """Start asyncio event loop in a background thread."""
        self._async_loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._async_thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name="async-loop",
        )
        self._async_thread.start()
        logger.info("Async event loop started")

    def _run_async(self, coro):
        """Schedule a coroutine on the background async loop."""
        if self._async_loop and self._async_loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return None

    def _init_client(self):
        """Initialize the Agent Zero HTTP client."""
        from agent_zero_client import AgentZeroClient
        url = self._config.get("agent_zero_url", "http://localhost:80")
        api_key = self._config.get("api_key", "")
        username = self._config.get("username", "")
        password = self._config.get("password", "")
        self._client = AgentZeroClient(
            url, api_key=api_key, username=username, password=password
        )

        # Restore context if keep_context is enabled
        if self._config.get("keep_context", True):
            saved_ctx = self._config.get("context_id", "")
            if saved_ctx:
                self._client.context_id = saved_ctx
                logger.info(f"Restored context: {saved_ctx}")

    def _init_overlay(self):
        """Initialize the floating overlay window."""
        from overlay import OverlayWindow
        self._overlay = OverlayWindow(
            on_send=self._on_send_message,
            on_new_chat=self._on_new_chat,
            config=self._config,
        )

    def _init_tray(self):
        """Initialize the system tray icon."""
        from tray import SystemTray
        self._tray = SystemTray(
            on_show=self._show_overlay,
            on_settings=self._show_settings,
            on_quit=self._quit,
            on_new_chat=self._on_new_chat,
        )
        if not self._tray.start():
            logger.warning("System tray not available")

    def _init_hotkey(self):
        """Register the global hotkey."""
        from hotkey_manager import HotkeyManager
        self._hotkey_manager = HotkeyManager()
        hotkey = self._config.get("hotkey", "<ctrl>+<space>")
        self._hotkey_manager.register(hotkey, self._on_hotkey)
        if not self._hotkey_manager.start():
            logger.warning(
                "Global hotkey registration failed. "
                "On macOS, grant Accessibility permissions: "
                "System Settings → Privacy & Security → Accessibility → enable Terminal"
            )

    def _on_hotkey(self):
        """Called when the global hotkey is pressed."""
        logger.debug("Hotkey triggered")
        # Must update UI from Qt main thread
        self._qt_invoke(self._show_overlay)

    def _show_overlay(self):
        """Show the overlay near the cursor (Qt main thread)."""
        if self._overlay:
            if self._overlay.is_visible:
                self._overlay.hide()
            else:
                # Auto-screenshot if configured
                if self._config.get("auto_screenshot", False):
                    from screen_capture import capture_screen
                    screenshot_path = capture_screen()
                    if screenshot_path:
                        self._overlay._screenshot_path = screenshot_path
                        self._overlay._screenshot_enabled = True
                self._overlay.show_near_cursor()

    def _show_settings(self):
        """Show the settings dialog (Qt main thread)."""
        self._qt_invoke(self._show_settings_qt)

    def _show_settings_qt(self):
        """Show settings dialog - must be called from Qt thread."""
        from settings_dialog import SettingsDialog
        dialog = SettingsDialog(
            config=self._config,
            on_save=self._on_settings_saved,
        )
        dialog.show()

    def _on_settings_saved(self, updates: dict):
        """Handle settings save - reinitialize affected components."""
        logger.info("Settings updated, reinitializing components")

        # Reinitialize client with new URL/key
        self._init_client()

        # Restart hotkey with new combination
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        self._init_hotkey()

        # Reinitialize overlay with new settings
        self._init_overlay()

        logger.info("Components reinitialized")

    def _on_send_message(self, text: str, screenshot_path: Optional[str] = None):
        """Handle message send from overlay. Runs in Qt thread, dispatches to async."""
        logger.info(f"Sending message: {text[:50]}..." if len(text) > 50 else f"Sending: {text}")

        # Update overlay status
        if self._overlay:
            self._overlay.set_status("Agent Zero denkt...", "#7b8cde")

        # Run async send in background
        future = self._run_async(
            self._send_message_async(text, screenshot_path)
        )

    async def _send_message_async(self, text: str, screenshot_path: Optional[str]):
        """Async message send and response handling."""
        try:
            response = await self._client.send_message(
                text=text,
                screenshot_path=screenshot_path,
            )

            # Save context ID
            if self._client.context_id and self._config.get("keep_context", True):
                self._config.set("context_id", self._client.context_id)

            # Update UI from Qt thread
            self._qt_invoke(lambda: self._on_response_received(response))

        except Exception as e:
            logger.error(f"Message send failed: {e}")
            error_msg = f"Fehler: {str(e)}"
            self._qt_invoke(lambda: self._on_response_error(error_msg))
        finally:
            # Clean up screenshot
            if screenshot_path:
                from screen_capture import cleanup_screenshot
                cleanup_screenshot(screenshot_path)

    def _on_response_received(self, response: str):
        """Handle received response (Qt main thread)."""
        if self._overlay:
            self._overlay.set_response(response)
            self._overlay.set_status("Antwort erhalten ✓", "#44ff44")

        # TTS if enabled
        if self._config.get("voice_output_enabled", True) and response:
            self._run_async(self._speak_response(response))

        # Tray notification
        if self._tray:
            preview = response[:80] + "..." if len(response) > 80 else response
            self._tray.notify("Agent Zero", preview)

    def _on_response_error(self, error: str):
        """Handle response error (Qt main thread)."""
        if self._overlay:
            self._overlay.set_status(error, "#ff4444")
            self._overlay.set_response(f"❌ {error}")

    async def _speak_response(self, text: str):
        """Speak the response using TTS."""
        try:
            from voice_output import get_tts_engine
            voice = self._config.get("voice_output_voice", "de-DE-KatjaNeural")
            tts = get_tts_engine(voice)
            tts.set_voice(voice)
            await tts.speak(text)
        except Exception as e:
            logger.error(f"TTS failed: {e}")

    def _on_new_chat(self):
        """Reset conversation context."""
        if self._client:
            self._client.reset_context()
        self._config.set("context_id", "")
        logger.info("Conversation context reset")

    def _qt_invoke(self, func):
        """Schedule a function call on the Qt main thread."""
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, func)
        except Exception as e:
            logger.error(f"Qt invoke failed: {e}")

    def _quit(self):
        """Quit the application."""
        logger.info("Quitting Agent Zero Companion")
        self._cleanup()
        if self._app:
            self._app.quit()

    def _cleanup(self):
        """Clean up resources."""
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        if self._tray:
            self._tray.stop()
        if self._async_loop:
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._client:
            # Schedule client close
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._client.close(), self._async_loop
                )
                future.result(timeout=2.0)
            except Exception:
                pass
        logger.info("Cleanup complete")


def main():
    """Application entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent Zero Companion - Desktop AI Assistant"
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open settings dialog on startup",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    app = AgentZeroCompanion()
    sys.exit(app.run(open_settings=args.settings))


if __name__ == "__main__":
    main()
