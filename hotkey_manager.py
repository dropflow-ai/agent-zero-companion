"""Global hotkey manager using pynput for cross-platform support."""
import logging
import threading
from typing import Callable, Optional, Set

logger = logging.getLogger(__name__)


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
        try:
            from pynput import keyboard

            if self._running:
                return True

            # Build pynput hotkey map
            hotkey_map = {}
            with self._lock:
                for combo, cb in self._hotkeys.items():
                    # pynput uses the same format we use
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

    def restart(self) -> bool:
        """Restart the listener (needed after registering new hotkeys)."""
        self.stop()
        return self.start()

    def _parse_hotkey(self, hotkey: str) -> Optional[list]:
        """Parse and validate a hotkey string."""
        try:
            from pynput import keyboard
            parts = hotkey.split("+")
            parsed = []
            for part in parts:
                part = part.strip()
                if part.startswith("<") and part.endswith(">"):
                    # Special key like <ctrl>, <alt>, <space>
                    key_name = part[1:-1]
                    key = getattr(keyboard.Key, key_name, None)
                    if key is None:
                        logger.warning(f"Unknown special key: {part}")
                        return None
                    parsed.append(key)
                else:
                    # Regular character key
                    parsed.append(keyboard.KeyCode.from_char(part))
            return parsed
        except Exception as e:
            logger.error(f"Hotkey parse error: {e}")
            return None

    @property
    def is_running(self) -> bool:
        return self._running

    def get_registered_hotkeys(self) -> list[str]:
        """Return list of currently registered hotkey strings."""
        with self._lock:
            return list(self._hotkeys.keys())


def format_hotkey_display(hotkey: str) -> str:
    """
    Convert internal hotkey format to human-readable display.
    e.g., '<ctrl>+<space>' → 'Ctrl + Space'
    """
    replacements = {
        "<ctrl>": "Ctrl",
        "<alt>": "Alt",
        "<shift>": "Shift",
        "<space>": "Space",
        "<enter>": "Enter",
        "<tab>": "Tab",
        "<esc>": "Esc",
        "<f1>": "F1", "<f2>": "F2", "<f3>": "F3", "<f4>": "F4",
        "<f5>": "F5", "<f6>": "F6", "<f7>": "F7", "<f8>": "F8",
        "<f9>": "F9", "<f10>": "F10", "<f11>": "F11", "<f12>": "F12",
        "<cmd>": "Cmd", "<super>": "Super",
    }
    result = hotkey
    for key, display in replacements.items():
        result = result.replace(key, display)
    return result.replace("+", " + ")


def parse_hotkey_from_display(display: str) -> str:
    """
    Convert human-readable hotkey back to internal format.
    e.g., 'Ctrl + Space' → '<ctrl>+<space>'
    """
    replacements = {
        "Ctrl": "<ctrl>",
        "Alt": "<alt>",
        "Shift": "<shift>",
        "Space": "<space>",
        "Enter": "<enter>",
        "Tab": "<tab>",
        "Esc": "<esc>",
        "F1": "<f1>", "F2": "<f2>", "F3": "<f3>", "F4": "<f4>",
        "F5": "<f5>", "F6": "<f6>", "F7": "<f7>", "F8": "<f8>",
        "F9": "<f9>", "F10": "<f10>", "F11": "<f11>", "F12": "<f12>",
        "Cmd": "<cmd>", "Super": "<super>",
    }
    # Remove spaces around +
    result = display.replace(" + ", "+").replace(" +", "+").replace("+ ", "+")
    for display_key, internal in replacements.items():
        result = result.replace(display_key, internal)
    return result.lower()
