"""Settings dialog for Agent Zero Companion using PyQt6."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


DIALOG_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
    font-size: 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel#section_label {
    color: #7b8cde;
    font-size: 13px;
    font-weight: bold;
    padding-top: 8px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #16213e;
    color: #ffffff;
    border: 1px solid #4a4a8a;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
    min-height: 28px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #7b8cde;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #7b8cde;
    margin-right: 6px;
}
QCheckBox {
    color: #e0e0e0;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4a4a8a;
    border-radius: 3px;
    background-color: #16213e;
}
QCheckBox::indicator:checked {
    background-color: #7b8cde;
    border-color: #7b8cde;
}
QPushButton {
    background-color: #4a4a8a;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-family: 'Segoe UI', Arial, sans-serif;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #6a6aaa;
}
QPushButton#save_btn {
    background-color: #7b8cde;
    font-weight: bold;
}
QPushButton#save_btn:hover {
    background-color: #9baefe;
}
QPushButton#test_btn {
    background-color: #2d5a27;
}
QPushButton#test_btn:hover {
    background-color: #3d7a37;
}
QFrame#separator {
    background-color: #4a4a8a;
    max-height: 1px;
}
QGroupBox {
    color: #7b8cde;
    border: 1px solid #4a4a8a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    font-size: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
"""


class SettingsDialog:
    """Settings dialog for configuring Agent Zero Companion."""

    def __init__(self, config, on_save=None):
        self.config = config
        self.on_save = on_save
        self._dialog = None
        self._hotkey_capture = False
        self._captured_keys = []

    def show(self):
        """Show the settings dialog."""
        try:
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is None:
                return
            self._build_dialog()
            if self._dialog:
                self._dialog.exec()
        except Exception as e:
            logger.error(f"Failed to show settings: {e}")

    def _build_dialog(self):
        """Build the settings dialog."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
            QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
            QGroupBox, QFrame, QSpinBox, QDoubleSpinBox,
            QDialogButtonBox, QMessageBox, QTabWidget, QWidget,
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence

        dialog = QDialog()
        dialog.setWindowTitle("Agent Zero Companion – Einstellungen")
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet(DIALOG_STYLE)
        dialog.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Tab widget
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #4a4a8a; border-radius: 6px; }
            QTabBar::tab { background: #16213e; color: #888; padding: 8px 16px;
                           border-radius: 4px 4px 0 0; margin-right: 2px; }
            QTabBar::tab:selected { background: #4a4a8a; color: #fff; }
        """)

        # ── Tab 1: Connection ──────────────────────────────────────────────
        conn_tab = QWidget()
        conn_layout = QFormLayout(conn_tab)
        conn_layout.setSpacing(10)
        conn_layout.setContentsMargins(16, 16, 16, 16)

        self._url_field = QLineEdit(self.config.get("agent_zero_url", "http://localhost:80"))
        self._url_field.setPlaceholderText("http://localhost:80 oder https://vps.example.com")
        conn_layout.addRow("Agent Zero URL:", self._url_field)

        self._api_key_field = QLineEdit(self.config.get("api_key", ""))
        self._api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_field.setPlaceholderText("Optional: API-Schlüssel (MCP Server Token)")
        conn_layout.addRow("API-Schlüssel:", self._api_key_field)

        # Login credentials (for session-based auth)
        self._username_field = QLineEdit(self.config.get("username", ""))
        self._username_field.setPlaceholderText("Agent Zero Login-Benutzername")
        conn_layout.addRow("Benutzername:", self._username_field)

        self._password_field = QLineEdit(self.config.get("password", ""))
        self._password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_field.setPlaceholderText("Agent Zero Login-Passwort")
        conn_layout.addRow("Passwort:", self._password_field)

        test_btn = QPushButton("Verbindung testen")
        test_btn.setObjectName("test_btn")
        test_btn.clicked.connect(self._test_connection)
        conn_layout.addRow("", test_btn)

        self._keep_context = QCheckBox("Gesprächskontext beibehalten")
        self._keep_context.setChecked(self.config.get("keep_context", True))
        conn_layout.addRow("", self._keep_context)

        tabs.addTab(conn_tab, "🔗 Verbindung")

        # ── Tab 2: Hotkey ──────────────────────────────────────────────────
        hotkey_tab = QWidget()
        hotkey_layout = QFormLayout(hotkey_tab)
        hotkey_layout.setSpacing(10)
        hotkey_layout.setContentsMargins(16, 16, 16, 16)

        from hotkey_manager import format_hotkey_display
        current_hotkey = self.config.get("hotkey", "<ctrl>+<space>")
        self._hotkey_field = QLineEdit(format_hotkey_display(current_hotkey))
        self._hotkey_field.setPlaceholderText("z.B. Ctrl + Space")
        self._hotkey_field.setReadOnly(True)
        self._hotkey_field.mousePressEvent = lambda e: self._start_hotkey_capture()

        hotkey_hint = QLabel("Klicken Sie auf das Feld und drücken Sie die gewünschte Tastenkombination")
        hotkey_hint.setStyleSheet("color: #888; font-size: 11px;")
        hotkey_hint.setWordWrap(True)

        hotkey_layout.addRow("Hotkey:", self._hotkey_field)
        hotkey_layout.addRow("", hotkey_hint)

        self._auto_screenshot = QCheckBox("Screenshot automatisch anhängen")
        self._auto_screenshot.setChecked(self.config.get("auto_screenshot", False))
        hotkey_layout.addRow("", self._auto_screenshot)

        tabs.addTab(hotkey_tab, "⌨ Hotkey")

        # ── Tab 3: Voice ───────────────────────────────────────────────────
        voice_tab = QWidget()
        voice_layout = QFormLayout(voice_tab)
        voice_layout.setSpacing(10)
        voice_layout.setContentsMargins(16, 16, 16, 16)

        self._voice_input_enabled = QCheckBox("Spracheingabe aktivieren")
        self._voice_input_enabled.setChecked(self.config.get("voice_input_enabled", True))
        voice_layout.addRow("", self._voice_input_enabled)

        self._whisper_model = QComboBox()
        for model in ["tiny", "base", "small", "medium", "large"]:
            self._whisper_model.addItem(model)
        current_model = self.config.get("whisper_model", "base")
        idx = self._whisper_model.findText(current_model)
        if idx >= 0:
            self._whisper_model.setCurrentIndex(idx)
        voice_layout.addRow("Whisper-Modell:", self._whisper_model)

        self._language = QComboBox()
        languages = [("de", "Deutsch"), ("en", "English"), ("fr", "Français"),
                     ("es", "Español"), ("it", "Italiano"), ("auto", "Automatisch")]
        for code, name in languages:
            self._language.addItem(name, code)
        current_lang = self.config.get("language", "de")
        for i in range(self._language.count()):
            if self._language.itemData(i) == current_lang:
                self._language.setCurrentIndex(i)
                break
        voice_layout.addRow("Sprache:", self._language)

        # TTS
        self._voice_output_enabled = QCheckBox("Sprachausgabe aktivieren (TTS)")
        self._voice_output_enabled.setChecked(self.config.get("voice_output_enabled", True))
        voice_layout.addRow("", self._voice_output_enabled)

        from voice_output import ALL_VOICES
        self._tts_voice = QComboBox()
        for v in ALL_VOICES:
            self._tts_voice.addItem(v)
        current_voice = self.config.get("voice_output_voice", "de-DE-KatjaNeural")
        idx = self._tts_voice.findText(current_voice)
        if idx >= 0:
            self._tts_voice.setCurrentIndex(idx)
        voice_layout.addRow("TTS-Stimme:", self._tts_voice)

        tabs.addTab(voice_tab, "🎤 Stimme")

        # ── Tab 4: Appearance ──────────────────────────────────────────────
        appear_tab = QWidget()
        appear_layout = QFormLayout(appear_tab)
        appear_layout.setSpacing(10)
        appear_layout.setContentsMargins(16, 16, 16, 16)

        self._overlay_width = QSpinBox()
        self._overlay_width.setRange(300, 800)
        self._overlay_width.setValue(self.config.get("overlay_width", 480))
        self._overlay_width.setSuffix(" px")
        appear_layout.addRow("Overlay-Breite:", self._overlay_width)

        self._overlay_opacity = QDoubleSpinBox()
        self._overlay_opacity.setRange(0.5, 1.0)
        self._overlay_opacity.setSingleStep(0.05)
        self._overlay_opacity.setValue(self.config.get("overlay_opacity", 0.95))
        appear_layout.addRow("Transparenz:", self._overlay_opacity)

        tabs.addTab(appear_tab, "🎨 Aussehen")

        layout.addWidget(tabs)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(dialog.reject)

        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("save_btn")
        save_btn.clicked.connect(lambda: self._save(dialog))

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._dialog = dialog

    def _start_hotkey_capture(self):
        """Start capturing a new hotkey combination."""
        if self._hotkey_field:
            self._hotkey_field.setText("Drücken Sie eine Tastenkombination...")
            self._hotkey_field.setStyleSheet("border: 1px solid #ff4444; color: #ff4444;")

            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QKeyEvent

            captured = []

            def key_press(event):
                modifiers = []
                mods = event.modifiers()
                if mods & Qt.KeyboardModifier.ControlModifier:
                    modifiers.append("<ctrl>")
                if mods & Qt.KeyboardModifier.AltModifier:
                    modifiers.append("<alt>")
                if mods & Qt.KeyboardModifier.ShiftModifier:
                    modifiers.append("<shift>")
                if mods & Qt.KeyboardModifier.MetaModifier:
                    modifiers.append("<cmd>")

                key = event.key()
                key_map = {
                    Qt.Key.Key_Space: "<space>",
                    Qt.Key.Key_Return: "<enter>",
                    Qt.Key.Key_Tab: "<tab>",
                    Qt.Key.Key_Escape: None,  # Cancel
                    Qt.Key.Key_F1: "<f1>", Qt.Key.Key_F2: "<f2>",
                    Qt.Key.Key_F3: "<f3>", Qt.Key.Key_F4: "<f4>",
                    Qt.Key.Key_F5: "<f5>", Qt.Key.Key_F6: "<f6>",
                    Qt.Key.Key_F7: "<f7>", Qt.Key.Key_F8: "<f8>",
                    Qt.Key.Key_F9: "<f9>", Qt.Key.Key_F10: "<f10>",
                    Qt.Key.Key_F11: "<f11>", Qt.Key.Key_F12: "<f12>",
                }

                if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt,
                           Qt.Key.Key_Shift, Qt.Key.Key_Meta):
                    return  # Modifier only, wait for main key

                if key == Qt.Key.Key_Escape:
                    # Cancel capture
                    from hotkey_manager import format_hotkey_display
                    self._hotkey_field.setText(
                        format_hotkey_display(self.config.get("hotkey", "<ctrl>+<space>"))
                    )
                    self._hotkey_field.setStyleSheet("")
                    self._hotkey_field.keyPressEvent = QKeyEvent.__init__
                    return

                key_str = key_map.get(key)
                if key_str is None and key < 128:
                    key_str = chr(key).lower()
                elif key_str is None:
                    return

                parts = modifiers + ([key_str] if key_str not in modifiers else [])
                hotkey = "+".join(parts)

                from hotkey_manager import format_hotkey_display
                self._hotkey_field.setText(format_hotkey_display(hotkey))
                self._hotkey_field.setStyleSheet("border: 1px solid #44ff44; color: #44ff44;")
                self._hotkey_field._captured_hotkey = hotkey
                self._hotkey_field.keyPressEvent = lambda e: None

            self._hotkey_field.keyPressEvent = key_press
            self._hotkey_field.setFocus()

    def _test_connection(self):
        """Test connection to Agent Zero."""
        import asyncio
        import threading
        from PyQt6.QtWidgets import QMessageBox

        url = self._url_field.text().strip()
        api_key = self._api_key_field.text().strip()
        username = self._username_field.text().strip()
        password = self._password_field.text().strip()

        def run_test():
            from agent_zero_client import AgentZeroClient
            client = AgentZeroClient(url, api_key=api_key, username=username, password=password)

            async def check():
                # Try login first if credentials provided
                if username:
                    logged_in = await client.login()
                    if not logged_in:
                        return False
                return await client.health_check()

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(check())
            loop.close()
            return result

        def test_thread():
            try:
                ok = run_test()
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                msg = "✅ Verbindung erfolgreich!" if ok else "❌ Verbindung fehlgeschlagen"
                # Show message box from main thread
                QMetaObject.invokeMethod(
                    self._dialog,
                    "setWindowTitle",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, msg),
                )
            except Exception as e:
                logger.error(f"Connection test error: {e}")

        threading.Thread(target=test_thread, daemon=True).start()

    def _save(self, dialog):
        """Save settings and close dialog."""
        from hotkey_manager import parse_hotkey_from_display

        # Get hotkey - use captured if available
        hotkey_display = self._hotkey_field.text()
        hotkey = getattr(self._hotkey_field, "_captured_hotkey",
                         parse_hotkey_from_display(hotkey_display))

        updates = {
            "agent_zero_url": self._url_field.text().strip(),
            "api_key": self._api_key_field.text().strip(),
            "username": self._username_field.text().strip(),
            "password": self._password_field.text().strip(),
            "hotkey": hotkey,
            "keep_context": self._keep_context.isChecked(),
            "auto_screenshot": self._auto_screenshot.isChecked(),
            "voice_input_enabled": self._voice_input_enabled.isChecked(),
            "whisper_model": self._whisper_model.currentText(),
            "language": self._language.currentData(),
            "voice_output_enabled": self._voice_output_enabled.isChecked(),
            "voice_output_voice": self._tts_voice.currentText(),
            "overlay_width": self._overlay_width.value(),
            "overlay_opacity": self._overlay_opacity.value(),
        }

        self.config.update(updates)
        logger.info("Settings saved")

        if self.on_save:
            self.on_save(updates)

        dialog.accept()
