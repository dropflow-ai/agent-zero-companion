"""Floating overlay UI for Agent Zero Companion using PyQt6."""
import asyncio
import logging
import os
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Dark theme stylesheet
DARK_STYLE = """
QWidget#overlay {
    background-color: #1a1a2e;
    border: 1px solid #4a4a8a;
    border-radius: 12px;
}
QWidget#header {
    background-color: #16213e;
    border-radius: 10px 10px 0 0;
    padding: 4px;
}
QLabel#title {
    color: #7b8cde;
    font-size: 11px;
    font-weight: bold;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel#status {
    color: #888;
    font-size: 10px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QTextEdit#response_area {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
    font-family: 'Segoe UI', Arial, sans-serif;
    selection-background-color: #4a4a8a;
}
QLineEdit#input_field {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #4a4a8a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLineEdit#input_field:focus {
    border: 1px solid #7b8cde;
}
QPushButton {
    background-color: #4a4a8a;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QPushButton:hover {
    background-color: #6a6aaa;
}
QPushButton:pressed {
    background-color: #3a3a7a;
}
QPushButton#send_btn {
    background-color: #7b8cde;
    font-weight: bold;
    min-width: 60px;
}
QPushButton#send_btn:hover {
    background-color: #9baefe;
}
QPushButton#voice_btn {
    background-color: #2d5a27;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    border-radius: 18px;
    font-size: 16px;
    padding: 0;
}
QPushButton#voice_btn:hover {
    background-color: #3d7a37;
}
QPushButton#voice_btn[recording=true] {
    background-color: #8b0000;
}
QPushButton#screenshot_btn {
    background-color: #1a3a5c;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    border-radius: 18px;
    font-size: 16px;
    padding: 0;
}
QPushButton#screenshot_btn:hover {
    background-color: #2a5a8c;
}
QPushButton#screenshot_btn[active=true] {
    background-color: #1a6a9c;
    border: 1px solid #7b8cde;
}
QPushButton#close_btn {
    background-color: transparent;
    color: #888;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    border-radius: 10px;
    font-size: 14px;
    padding: 0;
}
QPushButton#close_btn:hover {
    background-color: #8b0000;
    color: white;
}
QPushButton#new_chat_btn {
    background-color: transparent;
    color: #888;
    font-size: 11px;
    padding: 2px 6px;
}
QPushButton#new_chat_btn:hover {
    color: #aaa;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #4a4a8a;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class OverlayWindow:
    """
    Floating overlay window that appears near the cursor.
    Handles text input, voice recording, screenshot toggle, and response display.
    """

    def __init__(
        self,
        on_send: Callable[[str, Optional[str]], None],
        on_new_chat: Optional[Callable] = None,
        config=None,
    ):
        """
        Args:
            on_send: Callback(text, screenshot_path) called when user sends a message
            on_new_chat: Callback to reset the conversation context
            config: Config instance
        """
        self.on_send = on_send
        self.on_new_chat = on_new_chat
        self.config = config
        self._window = None
        self._app = None
        self._screenshot_path: Optional[str] = None
        self._screenshot_enabled = False
        self._recording = False
        self._recorder = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._status_label = None
        self._input_field = None
        self._response_area = None
        self._voice_btn = None
        self._screenshot_btn = None

    def _build_window(self):
        """Build the PyQt6 window. Must be called from the Qt thread."""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
            QLineEdit, QPushButton, QLabel, QSizePolicy,
            QGraphicsDropShadowEffect,
        )
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut

        width = self.config.get("overlay_width", 480) if self.config else 480
        opacity = self.config.get("overlay_opacity", 0.95) if self.config else 0.95

        # Main window
        win = QWidget()
        win.setObjectName("overlay")
        win.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        win.setWindowOpacity(opacity)
        win.setFixedWidth(width)
        win.setStyleSheet(DARK_STYLE)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        win.setGraphicsEffect(shadow)

        # Main layout
        main_layout = QVBoxLayout(win)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Inner container (for border radius)
        container = QWidget()
        container.setObjectName("overlay")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 12)
        container_layout.setSpacing(8)
        main_layout.addWidget(container)

        # --- Header ---
        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 4, 4)
        header_layout.setSpacing(6)

        title_label = QLabel("⚡ Agent Zero")
        title_label.setObjectName("title")

        self._status_label = QLabel("Bereit")
        self._status_label.setObjectName("status")

        new_chat_btn = QPushButton("+ Neu")
        new_chat_btn.setObjectName("new_chat_btn")
        new_chat_btn.setToolTip("Neues Gespräch starten")
        new_chat_btn.clicked.connect(self._on_new_chat)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setToolTip("Schließen (Esc)")
        close_btn.clicked.connect(self.hide)

        header_layout.addWidget(title_label)
        header_layout.addWidget(self._status_label)
        header_layout.addStretch()
        header_layout.addWidget(new_chat_btn)
        header_layout.addWidget(close_btn)
        container_layout.addWidget(header)

        # --- Response area ---
        self._response_area = QTextEdit()
        self._response_area.setObjectName("response_area")
        self._response_area.setReadOnly(True)
        self._response_area.setMinimumHeight(80)
        self._response_area.setMaximumHeight(400)
        self._response_area.setPlaceholderText(
            "Antwort von Agent Zero erscheint hier..."
        )
        self._response_area.hide()  # Hidden until first response
        container_layout.addWidget(self._response_area)

        # --- Input row ---
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        # Voice button
        self._voice_btn = QPushButton("🎤")
        self._voice_btn.setObjectName("voice_btn")
        self._voice_btn.setToolTip("Halten zum Aufnehmen")
        self._voice_btn.pressed.connect(self._start_recording)
        self._voice_btn.released.connect(self._stop_recording)
        if not (self.config and self.config.get("voice_input_enabled", True)):
            self._voice_btn.hide()

        # Screenshot button
        self._screenshot_btn = QPushButton("📷")
        self._screenshot_btn.setObjectName("screenshot_btn")
        self._screenshot_btn.setToolTip("Screenshot anhängen")
        self._screenshot_btn.setCheckable(True)
        self._screenshot_btn.clicked.connect(self._toggle_screenshot)
        if not (self.config and self.config.get("screenshot_enabled", True)):
            self._screenshot_btn.hide()

        # Text input
        self._input_field = QLineEdit()
        self._input_field.setObjectName("input_field")
        self._input_field.setPlaceholderText("Nachricht eingeben...")
        self._input_field.returnPressed.connect(self._on_send)

        # Send button
        send_btn = QPushButton("Senden")
        send_btn.setObjectName("send_btn")
        send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self._voice_btn)
        input_row.addWidget(self._screenshot_btn)
        input_row.addWidget(self._input_field)
        input_row.addWidget(send_btn)
        container_layout.addLayout(input_row)

        # Escape shortcut
        esc = QShortcut(QKeySequence("Escape"), win)
        esc.activated.connect(self.hide)

        # Enable dragging
        win._drag_pos = None
        win.mousePressEvent = lambda e: self._mouse_press(e, win)
        win.mouseMoveEvent = lambda e: self._mouse_move(e, win)

        self._window = win
        self._input_field.setFocus()

    def _mouse_press(self, event, win):
        from PyQt6.QtCore import Qt
        if event.button() == Qt.MouseButton.LeftButton:
            win._drag_pos = event.globalPosition().toPoint() - win.frameGeometry().topLeft()

    def _mouse_move(self, event, win):
        from PyQt6.QtCore import Qt
        if event.buttons() == Qt.MouseButton.LeftButton and win._drag_pos:
            win.move(event.globalPosition().toPoint() - win._drag_pos)

    def show_near_cursor(self):
        """Show the overlay near the current cursor position."""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QCursor
            from PyQt6.QtCore import QPoint

            if self._window is None:
                self._build_window()

            # Get cursor position
            cursor_pos = QCursor.pos()
            screen = QApplication.primaryScreen()
            screen_geo = screen.availableGeometry()

            win_width = self._window.width()
            win_height = self._window.sizeHint().height()

            # Position near cursor, keeping within screen bounds
            x = cursor_pos.x() + 20
            y = cursor_pos.y() + 20

            # Adjust if off-screen
            if x + win_width > screen_geo.right():
                x = cursor_pos.x() - win_width - 20
            if y + win_height > screen_geo.bottom():
                y = cursor_pos.y() - win_height - 20

            x = max(screen_geo.left(), x)
            y = max(screen_geo.top(), y)

            self._window.move(x, y)
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            self._input_field.setFocus()
            self._input_field.clear()
            self.set_status("Bereit")

        except Exception as e:
            logger.error(f"Failed to show overlay: {e}")

    def hide(self):
        """Hide the overlay."""
        if self._window:
            self._window.hide()
            # Clean up screenshot
            if self._screenshot_path:
                from screen_capture import cleanup_screenshot
                cleanup_screenshot(self._screenshot_path)
                self._screenshot_path = None
                self._screenshot_enabled = False
                if self._screenshot_btn:
                    self._screenshot_btn.setChecked(False)
                    self._screenshot_btn.setProperty("active", False)
                    self._screenshot_btn.style().unpolish(self._screenshot_btn)
                    self._screenshot_btn.style().polish(self._screenshot_btn)

    def set_status(self, text: str, color: str = "#888"):
        """Update the status label."""
        if self._status_label:
            self._status_label.setText(text)
            self._status_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def set_response(self, text: str):
        """Display a response in the response area."""
        if self._response_area:
            self._response_area.setMarkdown(text)
            self._response_area.show()
            # Auto-resize
            doc_height = int(self._response_area.document().size().height())
            clamped = max(80, min(doc_height + 20, 400))
            self._response_area.setFixedHeight(clamped)

    def append_response(self, text: str):
        """Append text to the response area."""
        if self._response_area:
            current = self._response_area.toPlainText()
            self._response_area.setPlainText(current + text)
            self._response_area.show()

    def set_input_text(self, text: str):
        """Set the input field text (e.g., from voice transcription)."""
        if self._input_field:
            self._input_field.setText(text)
            self._input_field.setFocus()

    def _on_send(self):
        """Handle send button click or Enter key."""
        if not self._input_field:
            return
        text = self._input_field.text().strip()
        if not text:
            return

        self._input_field.clear()
        self.set_status("Wird gesendet...", "#7b8cde")
        self._response_area.setPlainText("")

        # Take screenshot if enabled
        screenshot_path = None
        if self._screenshot_enabled:
            from screen_capture import capture_screen
            screenshot_path = capture_screen()
            self.set_status("Screenshot aufgenommen ✓", "#7b8cde")

        # Call the send callback
        if self.on_send:
            self.on_send(text, screenshot_path)

    def _on_new_chat(self):
        """Reset conversation context."""
        if self.on_new_chat:
            self.on_new_chat()
        self._response_area.setPlainText("")
        self._response_area.hide()
        self.set_status("Neues Gespräch", "#7b8cde")

    def _toggle_screenshot(self):
        """Toggle screenshot attachment."""
        self._screenshot_enabled = self._screenshot_btn.isChecked()
        self._screenshot_btn.setProperty("active", self._screenshot_enabled)
        self._screenshot_btn.style().unpolish(self._screenshot_btn)
        self._screenshot_btn.style().polish(self._screenshot_btn)
        if self._screenshot_enabled:
            self.set_status("Screenshot wird angehängt", "#7b8cde")
        else:
            self.set_status("Bereit")

    def _start_recording(self):
        """Start voice recording."""
        try:
            from voice_input import get_recorder
            self._recorder = get_recorder()
            if self._recorder.start():
                self._recording = True
                self._voice_btn.setProperty("recording", True)
                self._voice_btn.style().unpolish(self._voice_btn)
                self._voice_btn.style().polish(self._voice_btn)
                self._voice_btn.setText("⏹")
                self.set_status("Aufnahme läuft...", "#ff4444")
        except Exception as e:
            logger.error(f"Recording start failed: {e}")
            self.set_status("Mikrofon-Fehler", "#ff4444")

    def _stop_recording(self):
        """Stop voice recording and transcribe."""
        if not self._recording or not self._recorder:
            return

        self._recording = False
        self._voice_btn.setProperty("recording", False)
        self._voice_btn.style().unpolish(self._voice_btn)
        self._voice_btn.style().polish(self._voice_btn)
        self._voice_btn.setText("🎤")
        self.set_status("Transkribiere...", "#7b8cde")

        audio_path = self._recorder.stop()
        if not audio_path:
            self.set_status("Keine Aufnahme", "#ff4444")
            return

        # Transcribe in background thread
        def transcribe_thread():
            try:
                from voice_input import get_transcriber
                model = self.config.get("whisper_model", "base") if self.config else "base"
                lang = self.config.get("language", "de") if self.config else "de"
                transcriber = get_transcriber(model_size=model, language=lang)
                text = transcriber.transcribe(audio_path)

                # Update UI from main thread
                if text and self._input_field:
                    from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(
                        self._input_field,
                        "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, text),
                    )
                    self._update_status_queued("Transkription fertig ✓", "#44ff44")
                else:
                    self._update_status_queued("Keine Sprache erkannt", "#ff4444")

                # Cleanup
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            except Exception as e:
                logger.error(f"Transcription thread error: {e}")
                self._update_status_queued("Transkriptions-Fehler", "#ff4444")

        threading.Thread(target=transcribe_thread, daemon=True).start()

    def _update_status_queued(self, text: str, color: str = "#888"):
        """Thread-safe status update."""
        try:
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self._status_label,
                "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, text),
            )
        except Exception:
            pass

    def update_from_thread(self, func: Callable):
        """Schedule a UI update from a non-Qt thread."""
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, func)
        except Exception as e:
            logger.error(f"Thread update failed: {e}")

    @property
    def is_visible(self) -> bool:
        return self._window is not None and self._window.isVisible()
