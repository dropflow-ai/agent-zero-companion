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
| 📸 **Screenshot** | Attach a screenshot of your screen to any message |
| 🎤 **Voice Input** | Local Whisper STT — no cloud required |
| 🔊 **Voice Output** | Microsoft edge-tts — free, high-quality TTS |
| 🔗 **Local or Remote** | Connect to localhost or a remote VPS |
| 💬 **Context Memory** | Conversation context persists across hotkey activations |
| 🗂️ **System Tray** | Lives in your system tray, always ready |
| ⚙️ **Settings Dialog** | Full GUI settings — no config file editing needed |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Clone or download the project
cd agent-zero-companion

# Install Python dependencies
pip install -r requirements.txt

# Generate the app icon
python create_icon.py
```

### 2. Run

```bash
# First run — opens settings dialog automatically
python main.py

# Or explicitly open settings
python main.py --settings

# Debug mode (shows console output)
python main.py --debug
```

### 3. Configure

On first launch, the settings dialog opens automatically. Configure:

- **Agent Zero URL**: `http://localhost:80` (local) or `https://your-vps.com` (remote)
- **API Key**: Optional, if your Agent Zero instance requires authentication
- **Hotkey**: Click the field and press your desired key combination
- **Voice**: Enable/disable STT and TTS, choose Whisper model and TTS voice

---

## 📦 Requirements

### System Requirements

| Platform | Requirements |
|---|---|
| **Windows** | Windows 10/11, Python 3.11+ |
| **macOS** | macOS 12+, Python 3.11+ |
| **Linux** | X11 or Wayland, Python 3.11+, `libxcb` |

### Python Dependencies

```
PyQt6>=6.6.0          # UI framework
pystray>=0.19.5        # System tray
pynput>=1.7.6          # Global hotkeys
mss>=9.0.1             # Screen capture
Pillow>=10.0.0         # Image processing
httpx>=0.27.0          # HTTP client (async)
faster-whisper>=1.0.0  # Local STT
edge-tts>=6.1.9        # Free TTS
sounddevice>=0.4.6     # Audio recording
soundfile>=0.12.1      # Audio file I/O
numpy>=1.24.0          # Audio processing
```

### Linux Additional Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libportaudio2 \
    python3-pyaudio

# Fedora/RHEL
sudo dnf install -y \
    xcb-util-cursor \
    portaudio
```

---

## 🏗️ Architecture

```
agent-zero-companion/
├── main.py               # Entry point, orchestrates all components
├── config.py             # Configuration management (JSON persistence)
├── overlay.py            # PyQt6 floating overlay window
├── tray.py               # System tray icon (pystray)
├── hotkey_manager.py     # Global hotkey registration (pynput)
├── agent_zero_client.py  # HTTP client for Agent Zero API
├── screen_capture.py     # Screenshot capture (mss)
├── voice_input.py        # Whisper STT recording
├── voice_output.py       # edge-tts TTS playback
├── settings_dialog.py    # PyQt6 settings dialog
├── create_icon.py        # Icon generator (Pillow)
├── build.py              # PyInstaller build script
├── requirements.txt      # Python dependencies
└── assets/
    ├── icon.png          # App icon (256x256)
    ├── icon.ico          # Windows icon
    └── icon_mac.png      # macOS icon source
```

### Component Flow

```
[Global Hotkey]
      │
      ▼
[Overlay Window] ──── user types / speaks ────▶ [Agent Zero Client]
      │                                                  │
      │◀──────────── response text ─────────────────────┘
      │
      ├──▶ [TTS Engine]  (speaks response)
      └──▶ [Tray Notification]
```

---

## ⚙️ Configuration

Settings are stored in `~/.agent-zero-companion/config.json`.

| Setting | Default | Description |
|---|---|---|
| `agent_zero_url` | `http://localhost:80` | Agent Zero server URL |
| `api_key` | `""` | Optional API key |
| `hotkey` | `<ctrl>+<space>` | Global hotkey combination |
| `keep_context` | `true` | Persist conversation context |
| `auto_screenshot` | `false` | Auto-attach screenshot on open |
| `voice_input_enabled` | `true` | Enable Whisper STT |
| `whisper_model` | `base` | Whisper model size |
| `language` | `de` | STT language |
| `voice_output_enabled` | `true` | Enable TTS |
| `voice_output_voice` | `de-DE-KatjaNeural` | TTS voice |
| `overlay_width` | `480` | Overlay width in pixels |
| `overlay_opacity` | `0.95` | Overlay transparency |

### Hotkey Format

Hotkeys use pynput format:
- `<ctrl>+<space>` — Ctrl + Space
- `<alt>+<f1>` — Alt + F1
- `<ctrl>+<shift>+a` — Ctrl + Shift + A
- `<cmd>+<space>` — Cmd + Space (macOS)

---

## 🔨 Building Executables

### Prerequisites

```bash
pip install pyinstaller
```

### Build

```bash
# Build for current platform (directory output)
python build.py

# Single executable file
python build.py --onefile

# Debug build (with console window)
python build.py --debug
```

### Output

| Platform | Output |
|---|---|
| Windows | `dist/agent-zero-companion/agent-zero-companion.exe` |
| macOS | `dist/agent-zero-companion/agent-zero-companion` |
| Linux | `dist/agent-zero-companion/agent-zero-companion` |

---

## 🔗 Connecting to Agent Zero

### Local Instance

```
URL: http://localhost:80
```

### Remote VPS (Hostinger / any VPS)

```
URL: https://your-vps-domain.com
     or
URL: http://your-vps-ip:80
```

If your Agent Zero instance is behind a reverse proxy with HTTPS, use `https://`.

### API Authentication

If your Agent Zero instance has API key authentication enabled, enter the key in the settings dialog. It will be sent as `Authorization: Bearer <key>` header.

---

## 🎤 Voice Features

### Speech-to-Text (Whisper)

Local Whisper runs entirely on your machine — no data sent to cloud.

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `tiny` | 75 MB | Fastest | Basic |
| `base` | 145 MB | Fast | Good |
| `small` | 466 MB | Medium | Better |
| `medium` | 1.5 GB | Slow | Best |

Recommended: `base` for everyday use, `small` for better accuracy.

### Text-to-Speech (edge-tts)

Free Microsoft TTS via edge-tts. German voices:
- `de-DE-KatjaNeural` — Female, natural
- `de-DE-ConradNeural` — Male, natural
- `de-AT-IngridNeural` — Austrian female
- `de-CH-LeniNeural` — Swiss female

---

## 🐛 Troubleshooting

### Hotkey not working
- **Linux**: May need to run with elevated permissions or install `python3-xlib`
- **macOS**: Grant Accessibility permissions in System Preferences → Security & Privacy
- **Windows**: Run as Administrator if hotkey conflicts with system shortcuts

### System tray not showing
- **Linux**: Install `libappindicator3-1` or use a compatible desktop environment
- Try: `sudo apt-get install gir1.2-appindicator3-0.1`

### Voice input not working
- Check microphone permissions
- Install PortAudio: `sudo apt-get install libportaudio2` (Linux)
- Try a smaller Whisper model (`tiny`) if memory is limited

### Connection refused
- Verify Agent Zero is running and accessible
- Check firewall rules for the port
- Try `curl http://your-url/api/health` to test connectivity

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Credits

- Inspired by [zippy-windows](https://github.com/Arnie936/zippy-windows) by Arnie936
- Built for [Agent Zero](https://github.com/frdel/agent-zero) by frdel
- TTS powered by [edge-tts](https://github.com/rany2/edge-tts)
- STT powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
