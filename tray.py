"""System tray icon for Agent Zero Companion using pystray."""
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent / "assets"


class SystemTray:
    """
    System tray icon that provides quick access to Agent Zero Companion.
    Runs in its own thread to avoid blocking the Qt event loop.
    """

    def __init__(
        self,
        on_show: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        on_new_chat: Optional[Callable] = None,
    ):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.on_new_chat = on_new_chat
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    def _load_icon(self):
        """Load the tray icon image."""
        from PIL import Image

        icon_path = ASSETS_DIR / "icon.png"
        if icon_path.exists():
            return Image.open(icon_path)

        # Generate a simple fallback icon
        return self._generate_icon()

    def _generate_icon(self):
        """Generate a simple icon programmatically if no icon file exists."""
        from PIL import Image, ImageDraw

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a circle background
        draw.ellipse([2, 2, size - 2, size - 2], fill=(26, 26, 46, 255))

        # Draw a lightning bolt (⚡)
        draw.polygon(
            [(32, 8), (20, 34), (30, 34), (22, 56), (44, 28), (34, 28), (42, 8)],
            fill=(123, 140, 222, 255),
        )

        return img

    def _build_menu(self):
        """Build the tray context menu."""
        import pystray

        items = [
            pystray.MenuItem(
                "⚡ Agent Zero öffnen",
                lambda icon, item: self._safe_call(self.on_show),
                default=True,
            ),
            pystray.MenuItem(
                "+ Neues Gespräch",
                lambda icon, item: self._safe_call(self.on_new_chat),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚙ Einstellungen",
                lambda icon, item: self._safe_call(self.on_settings),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "✕ Beenden",
                lambda icon, item: self._quit(icon),
            ),
        ]
        return pystray.Menu(*items)

    def _safe_call(self, callback: Optional[Callable]):
        """Safely call a callback, catching exceptions."""
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"Tray callback error: {e}")

    def _quit(self, icon):
        """Handle quit from tray menu."""
        icon.stop()
        self._safe_call(self.on_quit)

    def start(self) -> bool:
        """Start the system tray icon in a background thread."""
        try:
            import pystray

            icon_image = self._load_icon()
            menu = self._build_menu()

            self._icon = pystray.Icon(
                name="agent-zero-companion",
                icon=icon_image,
                title="Agent Zero Companion",
                menu=menu,
            )

            self._thread = threading.Thread(
                target=self._icon.run,
                daemon=True,
                name="tray-thread",
            )
            self._thread.start()
            logger.info("System tray started")
            return True

        except ImportError:
            logger.error("pystray not installed. Run: pip install pystray")
            return False
        except Exception as e:
            logger.error(f"Failed to start system tray: {e}")
            return False

    def stop(self):
        """Stop the system tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        logger.info("System tray stopped")

    def update_tooltip(self, text: str):
        """Update the tray icon tooltip."""
        if self._icon:
            try:
                self._icon.title = text
            except Exception:
                pass

    def notify(self, title: str, message: str):
        """Show a system notification (if supported by platform)."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug(f"Notification not supported: {e}")
