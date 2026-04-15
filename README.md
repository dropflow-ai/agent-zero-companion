# ⚡ Agent Zero Companion

A cross-platform desktop AI assistant that connects to your [Agent Zero](https://github.com/frdel/agent-zero) instance via a global hotkey. Inspired by [zippy-windows](https://github.com/Arnie936/zippy-windows), built for Agent Zero.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🖱️ **Global Hotkey** | Configurable hotkey (default: `Ctrl+Space`) opens the overlay anywhere |
| 🖼️ **Floating Overlay** | Minimal, frameless overlay appears near your cursor |
| 📸 **Auto-Screenshot** | Automatically captures your screen when overlay opens |
| 🎤 **Voice Input** | Speech-to-text via Google Speech API (free, online) |
| 🔊 **Voice Output** | Microsoft edge-tts — free, high-quality TTS |
| 🔗 **Local or Remote** | Connect to localhost or a remote VPS |
| 🔐 **Session Auth + CSRF** | Full authentication with Agent Zero (login + CSRF token) |
| 💬 **Context Memory** | Conversation context persists across hotkey activations |
| 🗂️ **System Tray** | Lives in your system tray, always ready |
| ⚙️ **Settings Dialog** | Full GUI settings — no config file editing needed |

---

## 🚀 Quick Start

### macOS

```bash
# Clone the project
git clone https://github.com/dropflow-ai/agent-zero-companion.git
cd agent-zero-companion

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz SpeechRecognition

# Generate the app icon
python3 create_icon.py

# First run — opens settings dialog
python3 main.py --settings
```

### Windows / Linux

```bash
# Clone the project
git clone https://github.com/dropflow-ai/agent-zero-companion.git
cd agent-zero-companion

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Generate the app icon
python create_icon.py

# First run
python main.py --settings
```

---

## ⚙️ Configuration

On first run, the settings dialog opens automatically. Configure:

| Setting | Description |
|---|---|
| **Agent Zero URL** | URL of your Agent Zero instance (e.g., `http://72.62.45.162:50080`) |
| **Benutzername** | Your Agent Zero login username |
| **Passwort** | Your Agent Zero login password |
| **Hotkey** | Global hotkey combination (default: `Ctrl+Space`) |
| **Auto-Screenshot** | Automatically capture screen when overlay opens (default: on) |
| **Sprache** | Language for voice input (default: `de`) |

Settings are stored in `~/.agent-zero-companion/config.json`.

---

## 🏗️ Architecture

```
agent-zero-companion/
├── main.py              # Entry point, orchestrates all components
├── config.py            # JSON configuration (~/.agent-zero-companion/config.json)
├── overlay.py           # PyQt6 Floating Overlay UI (frameless, near cursor)
├── tray.py              # System Tray Icon (QSystemTrayIcon on macOS, pystray on Linux/Windows)
├── hotkey_manager.py    # Global Hotkeys (PyObjC/NSEvent on macOS, pynput on Linux/Windows)
├── agent_zero_client.py # HTTP Client for Agent Zero API (Session Auth + CSRF)
├── screen_capture.py    # Screenshot capture (mss, all monitors)
├── voice_input.py       # Multi-backend STT (SpeechRecognition/Google API, optional faster-whisper)
├── voice_output.py      # edge-tts TTS (free, Microsoft)
├── settings_dialog.py   # PyQt6 Settings Dialog (4 tabs, incl. login fields)
├── create_icon.py       # Icon generator (Pillow)
├── build.py             # PyInstaller build script
├── start.command        # macOS double-click launcher (runs in background)
└── requirements.txt     # Python dependencies
```

---

## 🍎 macOS-Specific Notes

### Platform-Specific Implementations

| Component | macOS | Windows/Linux |
|---|---|---|
| **Hotkeys** | PyObjC NSEvent | pynput |
| **Tray Icon** | QSystemTrayIcon | pystray |
| **Voice Input** | SpeechRecognition (Google API) | SpeechRecognition / faster-whisper |

### Why PyObjC instead of pynput on macOS?

`pynput` runs a keyboard listener in a background thread using Cocoa/AppKit internally. This conflicts with PyQt6's main thread, causing a `SIGTRAP` crash when the hotkey is pressed. PyObjC's `NSEvent.addGlobalMonitorForEventsMatchingMask` integrates directly with the Qt/AppKit event loop — no background thread conflicts.

### Why QSystemTrayIcon instead of pystray on macOS?

`pystray` calls `NSApplication.run()` on a background thread, which conflicts with PyQt6's `QApplication` that also manages the NSApplication instance. Using PyQt6's built-in `QSystemTrayIcon` avoids this thread conflict entirely.

### Accessibility Permissions

Global hotkeys on macOS require **Accessibility** permissions:
1. Go to **System Settings → Privacy & Security → Accessibility**
2. Add **Terminal** (or your IDE) to the allowed list
3. Restart the application

---

## 📸 Screenshot Feature

When you press the hotkey to open the overlay:
1. A screenshot is **automatically captured** (before the overlay appears)
2. You see the status: `📷 Screenshot angehängt`
3. Type your question (e.g., "Was siehst du auf meinem Bildschirm?")
4. The screenshot is sent as a base64 attachment with your message
5. Agent Zero analyzes the image and responds

You can toggle auto-screenshot off via the 📷 button in the overlay.

---

## 🎤 Voice Input

Press the 🎤 button in the overlay to record voice input:
- **Default backend**: Google Speech API (free, online, no API key needed)
- **Optional**: Install `faster-whisper` for offline local transcription
- Language is configurable in settings (default: German)

---

## 📦 Building a Standalone App

### macOS (.app Bundle)

```bash
cd agent-zero-companion
source venv/bin/activate
pip install pyinstaller
python3 build.py
```

The `.app` bundle will be in `dist/agent-zero-companion.app`. Drag it to `/Applications/`.

> **Note:** macOS may block the app from an unverified developer. Go to **System Settings → Privacy & Security** and click **"Open Anyway"**.

### Running Without Terminal

**Option 1: Double-click launcher**
```bash
chmod +x start.command
# Then double-click start.command in Finder
```

**Option 2: Built .app from Applications folder**

---

## 🔗 Connecting to Agent Zero

1. Open settings (tray icon → Einstellungen, or `python3 main.py --settings`)
2. Enter your Agent Zero URL (e.g., `http://72.62.45.162:50080`)
3. Enter your login credentials (same as browser login)
4. Click **"Verbindung testen"** to verify

The app handles:
- Session-based authentication (login with username/password)
- CSRF token management (automatic)
- Session renewal on expiry (automatic)
- Context persistence across messages

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `zsh: command not found: python` | Use `python3` on macOS |
| `zsh: trace trap` on hotkey | Install PyObjC: `pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz` |
| Settings won't open | `git pull` and clear cache: `find . -name '*.pyc' -delete` |
| 403 Forbidden on API calls | Update app (`git pull`) — CSRF token support was added |
| Voice not recognized | `pip install SpeechRecognition` — needs internet connection |
| Screenshot not working | `pip install mss` |
| App blocked by macOS | System Settings → Privacy & Security → Open Anyway |

---

## 📋 Tech Stack

- **Python 3.11+**
- **PyQt6** — UI framework
- **httpx** — Async HTTP client
- **mss** — Cross-platform screenshot
- **SpeechRecognition** — Speech-to-text (Google API)
- **edge-tts** — Text-to-speech (Microsoft)
- **PyObjC** — macOS native integration (hotkeys, tray)
- **PyInstaller** — Standalone app building

---

## 📄 License

MIT License
