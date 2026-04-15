"""Global hotkey manager using pynput for cross-platform support."""
import logging
import platform
import sys
import threading
from typing import Callable, Optional, Set

logger = logging.getLogger(__name__)


def check_macos_accessibility() -> bool:
    """Check if Accessibility permissions are likely granted on macOS.
    Returns True if not on macOS or if permissions seem OK."""
    if platform.system() != "Darwin":
        return True
    try:
        # Try importing and creating a minimal listener to test permissions
        import subprocess
        # Use tccutil or check via AppleScript - but simplest is just to try
        return True  # We'll catch the actual error during start()
    except Exception:
        return False


def request_macos_accessibility():
    """Show a dialog requesting macOS Accessibility permissions."""
    if platform.system() != "Darwin":
        return
    try:
        import subprocess
        script = '''
        tell application "System Preferences"
            activate
            set current pane to pane "com.apple.preference.security"
            reveal anchor "Privacy_Accessibility" of pane "com.apple.preference.security"
        end tell
        '''
        # Try to open System Settings directly
        subprocess.Popen([
            "open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ])
    except Exception as e:
        logger.debug(f"Could not open System Preferences: {e}")


class HotkeyManager:
    """
    Manages global hotkeys using pynput.
    Supports configurable key combinations like <ctrl>+<space>, <alt>+<shift>+a, etc.

    Key format examples:
        '<ctrl>+<space>'       → Ctrl + Space
        '<alt>+<shift>+a'      → Alt + Shift + A
        '<ctrl>+<alt>+z'       → Ctrl + Alt + Z
        '<f12>'                → F12 alone
    """

    def __init__(self):
        self._hotkeys: dict[str, Callable] = {}
        self._listener = None
        self._running = False
        self._pressed_keys: Set = set()
        self._lock = threading.Lock()
        self._is_macos = platform.system() == "Darwin"

    def register(self, hotkey: str, callback: Callable) -> bool:
        """
        Register a hotkey combination with a callback.

        Args:
            hotkey: Key combination string (e.g., '<ctrl>+<space>')
            callback: Function to call when hotkey is pressed

        Returns:
            True if registered successfully
        """
        try:
            from pynput import keyboard

            # Validate the hotkey by parsing it
            parsed = self._parse_hotkey(hotkey)
            if not parsed:
                logger.error(f"Invalid hotkey format: {hotkey}")
                return False

            with self._lock:
                self._hotkeys[hotkey] = callback

            logger.info(f"Registered hotkey: {hotkey}")
            return True
        except ImportError:
            logger.error("pynput not installed. Run: pip install pynput")
            return False
        except Exception as e:
            logger.error(f"Failed to register hotkey {hotkey}: {e}")
            return False

    def unregister(self, hotkey: str) -> None:
        """Remove a registered hotkey."""
        with self._lock:
            self._hotkeys.pop(hotkey, None)
        logger.info(f"Unregistered hotkey: {hotkey}")

    def start(self) -> bool:
        """Start listening for hotkeys. Returns True if successful."""
        if self._is_macos:
            return self._start_macos()
        return self._start_default()

    def _start_macos(self) -> bool:
        """Start hotkey listener on macOS with permission handling."""
        try:
            from pynput import keyboard

            if self._running:
                return True

            # Build pynput hotkey map
            hotkey_map = {}
            with self._lock:
                for combo, cb in self._hotkeys.items():
                    hotkey_map[combo] = cb

            if not hotkey_map:
                logger.warning("No hotkeys registered")
                return False

            # On macOS, pynput needs Accessibility permissions.
            # If not granted, GlobalHotKeys will cause SIGTRAP.
            # We start the listener in a separate process to test.
            logger.info("macOS detected – testing Accessibility permissions...")

            # Try starting in a thread with a timeout
            success = [False]
            error = [None]

            def try_start():
                try:
                    listener = keyboard.GlobalHotKeys(hotkey_map)
                    listener.start()
                    # If we get here, permissions are OK
                    self._listener = listener
                    self._running = True
                    success[0] = True
                    logger.info(f"Hotkey listener started with {len(hotkey_map)} hotkeys")
                except Exception as e:
                    error[0] = e

            thread = threading.Thread(target=try_start, daemon=True)
            thread.start()
            thread.join(timeout=3.0)

            if success[0]:
                return True

            # If we get here, either timeout or error
            logger.warning(
                "⚠️  macOS Accessibility-Berechtigung fehlt!\n"
                "    Bitte erteile Terminal/Python die Berechtigung:\n"
                "    Systemeinstellungen → Datenschutz & Sicherheit → Bedienungshilfen\n"
                "    Füge 'Terminal' (oder 'iTerm') zur Liste hinzu und aktiviere es."
            )
            request_macos_accessibility()
            return False

        except ImportError:
            logger.error("pynput not installed. Run: pip install pynput")
            return False
        except Exception as e:
            logger.error(f"Failed to start hotkey listener: {e}")
            return False

    def _start_default(self) -> bool:
        """Start hotkey listener on Windows/Linux."""
        try:
            from pynput import keyboard

            if self._running:
                return True

            hotkey_map = {}
            with self._lock:
                for combo, cb in self._hotkeys.items():
                    hotkey_map[combo] = cb

            if not hotkey_map:
                logger.warning("No hotkeys registered")
                return False

            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
            self._running = True
            logger.info(f"Hotkey listener started with {len(hotkey_map)} hotkeys")
            return True

        except ImportError:
            logger.error("pynput not installed. Run: pip install pynput")
            return False
        except Exception as e:
            logger.error(f"Failed to start hotkey listener: {e}")
            return False

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False
        logger.info("Hotkey listener stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _parse_hotkey(self, hotkey: str) -> list:
        """Parse a hotkey string into key components."""
        parts = hotkey.split("+")
        return [p.strip() for p in parts if p.strip()]


def format_hotkey_display(hotkey: str) -> str:
    """Convert internal hotkey format to display format.
    '<ctrl>+<space>' → 'Ctrl + Space'
    """
    replacements = {
        "<ctrl>": "Ctrl",
        "<alt>": "Alt",
        "<shift>": "Shift",
        "<cmd>": "Cmd",
        "<space>": "Space",
        "<enter>": "Enter",
        "<tab>": "Tab",
        "<f1>": "F1", "<f2>": "F2", "<f3>": "F3", "<f4>": "F4",
        "<f5>": "F5", "<f6>": "F6", "<f7>": "F7", "<f8>": "F8",
        "<f9>": "F9", "<f10>": "F10", "<f11>": "F11", "<f12>": "F12",
    }
    parts = hotkey.split("+")
    display_parts = []
    for part in parts:
        part = part.strip()
        display_parts.append(replacements.get(part, part.upper()))
    return " + ".join(display_parts)


def parse_hotkey_from_display(display: str) -> str:
    """Convert display format back to internal format.
    'Ctrl + Space' → '<ctrl>+<space>'
    """
    replacements = {
        "ctrl": "<ctrl>",
        "alt": "<alt>",
        "shift": "<shift>",
        "cmd": "<cmd>",
        "space": "<space>",
        "enter": "<enter>",
        "tab": "<tab>",
        "f1": "<f1>", "f2": "<f2>", "f3": "<f3>", "f4": "<f4>",
        "f5": "<f5>", "f6": "<f6>", "f7": "<f7>", "f8": "<f8>",
        "f9": "<f9>", "f10": "<f10>", "f11": "<f11>", "f12": "<f12>",
    }
    parts = display.split("+")
    internal_parts = []
    for part in parts:
        part = part.strip().lower()
        internal_parts.append(replacements.get(part, part))
    return "+".join(internal_parts)
