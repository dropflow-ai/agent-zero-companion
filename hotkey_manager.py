"""Global hotkey manager.

macOS: Uses PyObjC NSEvent global monitor (runs on Qt/AppKit main thread).
Windows/Linux: Uses pynput GlobalHotKeys (runs in background thread).

pynput is NOT used on macOS because it runs Cocoa listeners in background
threads, causing SIGTRAP crashes when hotkey callbacks touch AppKit.
"""
import logging
import platform
import threading
from typing import Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Cross-platform global hotkey manager.

    Key format examples:
        '<ctrl>+<space>'       -> Ctrl + Space
        '<alt>+<shift>+a'      -> Alt + Shift + A
        '<cmd>+<space>'        -> Cmd + Space (macOS)
    """

    def __init__(self):
        self._hotkeys: Dict[str, Callable] = {}
        self._impl = None
        self._running = False

    def register(self, hotkey: str, callback: Callable) -> bool:
        """Register a hotkey combination with a callback."""
        self._hotkeys[hotkey] = callback
        logger.info(f"Registered hotkey: {hotkey}")
        return True

    def unregister(self, hotkey: str) -> None:
        """Remove a registered hotkey."""
        self._hotkeys.pop(hotkey, None)
        logger.info(f"Unregistered hotkey: {hotkey}")

    def start(self) -> bool:
        """Start listening for hotkeys."""
        if not self._hotkeys:
            logger.warning("No hotkeys registered")
            return False

        if platform.system() == "Darwin":
            self._impl = _MacOSHotkeyListener(self._hotkeys)
        else:
            self._impl = _PynputHotkeyListener(self._hotkeys)

        return self._impl.start()

    def stop(self):
        """Stop listening for hotkeys."""
        if self._impl:
            self._impl.stop()
            self._impl = None


# ---------------------------------------------------------------------------
# macOS: NSEvent global monitor via PyObjC
# Runs on the main thread's run loop (shared with Qt) – no SIGTRAP.
# ---------------------------------------------------------------------------

def _parse_hotkey_to_modifiers_and_key(hotkey_str: str):
    """Parse '<ctrl>+<space>' style string into (modifier_flags, key_code/char).

    Returns (modifier_mask, key_string) for NSEvent matching.
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]

    modifiers = 0
    key_part = None

    # macOS modifier flags (from NSEvent)
    # We'll import Cocoa constants inside the function to avoid import errors on non-mac
    modifier_map = {
        "<ctrl>": "control",
        "<control>": "control",
        "<shift>": "shift",
        "<alt>": "option",
        "<option>": "option",
        "<cmd>": "command",
        "<command>": "command",
        "<super>": "command",
    }

    active_mods = set()

    for part in parts:
        if part in modifier_map:
            active_mods.add(modifier_map[part])
        else:
            # This is the key
            key_part = part.strip("<>")

    return active_mods, key_part


class _MacOSHotkeyListener:
    """Global hotkey listener using PyObjC NSEvent monitor."""

    def __init__(self, hotkeys: Dict[str, Callable]):
        self._hotkeys = hotkeys
        self._monitor = None
        self._parsed_hotkeys = []  # list of (modifier_set, key, callback)

    def start(self) -> bool:
        try:
            import Cocoa
            import Quartz

            # Parse all hotkeys
            for combo, callback in self._hotkeys.items():
                mods, key = _parse_hotkey_to_modifiers_and_key(combo)
                if key:
                    self._parsed_hotkeys.append((mods, key, callback))
                    logger.debug(f"Parsed macOS hotkey: mods={mods} key={key}")

            if not self._parsed_hotkeys:
                logger.error("No valid hotkeys parsed")
                return False

            # Map modifier names to NSEvent modifier flags
            self._mod_flag_map = {
                "control": Cocoa.NSEventModifierFlagControl,
                "shift": Cocoa.NSEventModifierFlagShift,
                "option": Cocoa.NSEventModifierFlagOption,
                "command": Cocoa.NSEventModifierFlagCommand,
            }

            # Special key name to keyCode mapping
            self._special_keys = {
                "space": 49,
                "return": 36,
                "enter": 36,
                "tab": 48,
                "escape": 53,
                "esc": 53,
                "delete": 51,
                "backspace": 51,
                "f1": 122, "f2": 120, "f3": 99, "f4": 118,
                "f5": 96, "f6": 97, "f7": 98, "f8": 100,
                "f9": 101, "f10": 109, "f11": 103, "f12": 111,
                "up": 126, "down": 125, "left": 123, "right": 124,
            }

            # Register global monitor for keyDown events
            mask = Cocoa.NSEventMaskKeyDown

            def handler(event):
                self._handle_event(event)
                return event

            self._monitor = Cocoa.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                mask, handler
            )

            if self._monitor is None:
                logger.error(
                    "Failed to register global key monitor. "
                    "Grant Accessibility permissions: "
                    "System Settings → Privacy & Security → Accessibility → enable Terminal"
                )
                return False

            logger.info(f"Hotkey listener started (macOS NSEvent) with {len(self._parsed_hotkeys)} hotkeys")
            return True

        except ImportError as e:
            logger.error(f"PyObjC not available: {e}. Install with: pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz")
            return False
        except Exception as e:
            logger.error(f"Failed to start macOS hotkey listener: {e}")
            return False

    def _handle_event(self, event):
        """Check if the event matches any registered hotkey."""
        try:
            import Cocoa

            event_flags = event.modifierFlags()
            event_keycode = event.keyCode()

            # Try to get character
            try:
                event_chars = event.charactersIgnoringModifiers()
                event_char = event_chars.lower() if event_chars else None
            except Exception:
                event_char = None

            for mods, key, callback in self._parsed_hotkeys:
                # Check modifiers
                mods_match = True
                for mod_name in mods:
                    flag = self._mod_flag_map.get(mod_name, 0)
                    if not (event_flags & flag):
                        mods_match = False
                        break

                if not mods_match:
                    continue

                # Check key
                key_match = False

                # Check special keys by keyCode
                if key in self._special_keys:
                    if event_keycode == self._special_keys[key]:
                        key_match = True
                # Check character keys
                elif event_char and event_char == key:
                    key_match = True

                if key_match:
                    logger.debug(f"Hotkey matched: mods={mods} key={key}")
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Hotkey callback error: {e}")

        except Exception as e:
            logger.error(f"Error handling key event: {e}")

    def stop(self):
        if self._monitor:
            try:
                import Cocoa
                Cocoa.NSEvent.removeMonitor_(self._monitor)
            except Exception as e:
                logger.debug(f"Error removing monitor: {e}")
            self._monitor = None
        logger.info("macOS hotkey listener stopped")


# ---------------------------------------------------------------------------
# Windows / Linux: pynput GlobalHotKeys (background thread)
# ---------------------------------------------------------------------------

class _PynputHotkeyListener:
    """Global hotkey listener using pynput. Works on Windows and Linux."""

    def __init__(self, hotkeys: Dict[str, Callable]):
        self._hotkeys = hotkeys
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys(self._hotkeys)
            self._listener.start()
            logger.info(f"Hotkey listener started (pynput) with {len(self._hotkeys)} hotkeys")
            return True

        except ImportError:
            logger.error("pynput not installed. Run: pip install pynput")
            return False
        except Exception as e:
            logger.error(f"Failed to start pynput hotkey listener: {e}")
            return False

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        logger.info("pynput hotkey listener stopped")
