"""System tray icon for Agent Zero Companion.

Uses PyQt6 QSystemTrayIcon on macOS (pystray crashes because it runs
NSApplication.run() off the main thread, conflicting with Qt's event loop).
Uses pystray on Windows/Linux where it works reliably.
"""
import logging
import platform
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent / "assets"


class SystemTray:
    """
    System tray icon that provides quick access to Agent Zero Companion.
    Auto-selects the best backend for the current platform.
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
        self._impl = None

    def start(self) -> bool:
        """Start the system tray icon. Returns True if successful."""
        if platform.system() == "Darwin":
            self._impl = _QtTray(
                on_show=self.on_show,
                on_settings=self.on_settings,
                on_quit=self.on_quit,
                on_new_chat=self.on_new_chat,
            )
        else:
            self._impl = _PystrayTray(
                on_show=self.on_show,
                on_settings=self.on_settings,
                on_quit=self.on_quit,
                on_new_chat=self.on_new_chat,
            )
        return self._impl.start()

    def stop(self):
        """Stop the system tray icon."""
        if self._impl:
            self._impl.stop()


# ---------------------------------------------------------------------------
# macOS: PyQt6 QSystemTrayIcon (runs on Qt main thread – no AppKit conflict)
# ---------------------------------------------------------------------------

class _QtTray:
    """System tray using PyQt6 QSystemTrayIcon. Safe on macOS."""

    def __init__(self, on_show=None, on_settings=None, on_quit=None, on_new_chat=None):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.on_new_chat = on_new_chat
        self._tray_icon = None
        self._menu = None  # prevent garbage collection

    def start(self) -> bool:
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon, QAction
            from PyQt6.QtCore import QCoreApplication

            app = QCoreApplication.instance()
            if not app:
                logger.error("No QApplication instance – cannot create Qt tray")
                return False

            # Load icon
            icon_path = ASSETS_DIR / "icon.png"
            if icon_path.exists():
                icon = QIcon(str(icon_path))
            else:
                icon = self._generate_qt_icon()

            self._tray_icon = QSystemTrayIcon(icon)

            # Build context menu
            self._menu = QMenu()

            action_show = QAction("Agent Zero öffnen", self._menu)
            action_show.triggered.connect(lambda: self._safe_call(self.on_show))
            self._menu.addAction(action_show)

            action_new = QAction("Neues Gespräch", self._menu)
            action_new.triggered.connect(lambda: self._safe_call(self.on_new_chat))
            self._menu.addAction(action_new)

            self._menu.addSeparator()

            action_settings = QAction("Einstellungen", self._menu)
            action_settings.triggered.connect(lambda: self._safe_call(self.on_settings))
            self._menu.addAction(action_settings)

            self._menu.addSeparator()

            action_quit = QAction("Beenden", self._menu)
            action_quit.triggered.connect(lambda: self._safe_call(self.on_quit))
            self._menu.addAction(action_quit)

            self._tray_icon.setContextMenu(self._menu)

            # Click opens overlay
            self._tray_icon.activated.connect(self._on_activated)

            self._tray_icon.setToolTip("Agent Zero Companion")
            self._tray_icon.show()

            logger.info("System tray started (Qt backend)")
            return True

        except Exception as e:
            logger.error(f"Failed to start Qt tray: {e}")
            return False

    def _on_activated(self, reason):
        """Handle tray icon activation (click/double-click)."""
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._safe_call(self.on_show)

    def _generate_qt_icon(self):
        """Generate a simple fallback icon."""
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
        from PyQt6.QtCore import Qt, QRect

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circle background
        painter.setBrush(QBrush(QColor(26, 26, 46)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Draw "A0" text
        painter.setPen(QColor(123, 140, 222))
        font = painter.font()
        font.setPixelSize(24)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A0")

        painter.end()
        return QIcon(pixmap)

    def _safe_call(self, callback):
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"Tray callback error: {e}")

    def stop(self):
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None
        self._menu = None
        logger.info("Qt tray stopped")


# ---------------------------------------------------------------------------
# Windows / Linux: pystray (runs in its own thread)
# ---------------------------------------------------------------------------

class _PystrayTray:
    """System tray using pystray. Works on Windows and Linux."""

    def __init__(self, on_show=None, on_settings=None, on_quit=None, on_new_chat=None):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.on_new_chat = on_new_chat
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    def _load_icon(self):
        from PIL import Image
        icon_path = ASSETS_DIR / "icon.png"
        if icon_path.exists():
            return Image.open(icon_path)
        return self._generate_icon()

    def _generate_icon(self):
        from PIL import Image, ImageDraw
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, size - 2, size - 2], fill=(26, 26, 46, 255))
        draw.polygon(
            [(32, 8), (20, 34), (30, 34), (22, 56), (44, 28), (34, 28), (42, 8)],
            fill=(123, 140, 222, 255),
        )
        return img

    def _build_menu(self):
        import pystray
        items = [
            pystray.MenuItem(
                "Agent Zero öffnen",
                lambda icon, item: self._safe_call(self.on_show),
                default=True,
            ),
            pystray.MenuItem(
                "Neues Gespräch",
                lambda icon, item: self._safe_call(self.on_new_chat),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Einstellungen",
                lambda icon, item: self._safe_call(self.on_settings),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Beenden",
                lambda icon, item: self._quit(icon),
            ),
        ]
        return pystray.Menu(*items)

    def _safe_call(self, callback):
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"Tray callback error: {e}")

    def _quit(self, icon):
        icon.stop()
        self._safe_call(self.on_quit)

    def start(self) -> bool:
        try:
            import pystray
            image = self._load_icon()
            menu = self._build_menu()
            self._icon = pystray.Icon(
                "agent-zero-companion",
                image,
                "Agent Zero Companion",
                menu,
            )
            self._thread = threading.Thread(
                target=self._icon.run,
                daemon=True,
                name="tray-thread",
            )
            self._thread.start()
            logger.info("System tray started (pystray backend)")
            return True
        except Exception as e:
            logger.error(f"Failed to start pystray tray: {e}")
            return False

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        logger.info("Pystray tray stopped")
