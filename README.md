# Voice Flow (Flow STT) 🎙️⚡

A high-performance, privacy-first Speech-to-Text desktop application for Windows, engineered in the style of **Wispr Flow**.

Powered by **faster-whisper (CTranslate2 INT8)**, **PySide6 (Qt6)**, and an intelligent spoken text cleaner.

---

## 🌊 Wispr Flow Experience

- **Frosted Glass Floating Capsule**:
  - Discreet, floating stay-on-top capsule that never steals keyboard focus from your cursor.
  - **Real-Time Live Streaming Transcripts**: Spoken words stream live directly inside the capsule as you speak.
  - Live animated 60 FPS **fluid audio waveform** that bounces organically with your voice.
  - Live timer display (`0:04`) counting while speaking.
  - Shimmering `Flowing...` transition state and `✓ Pasted!` confirmation.
  - Built-in `✕` cancel button to discard audio on the fly.
  - Smooth mouse drag-and-drop to place the pill anywhere on your screen.

- **Wispr Flow AI Text Polish (Dual Mode: Offline Regex + Cloud LLM)**:
  - **Local Offline Mode (Default)**: Automatically eliminates verbal fillers (*"um"*, *"uh"*, *"you know"*), fixes stutters, and normalizes capitalization locally with zero network calls.
  - **Cloud AI Mode (MiMo / Qwen / Groq)**: Integrates cutting-edge fast models like `xiaomi/mimo-v2.6-flash` or `qwen/qwen3.8-omni-flash` for intelligent, context-aware rewriting, bullet points, emails, and natural prose.
  - **Resilient Fallback**: If the network is down or API fails, Flow instantly falls back to local regex so your dictation is never lost.

- **Procedural Audio Chimes**:
  - Pleasant, soft upward chime when you start dictating.
  - Soft chime when transcription finishes.
  - Crisp gentle chime when text is pasted.
  - 100% procedurally synthesized (zero bulky audio assets).

- **System-Wide Auto-Paste**:
  - Press `Ctrl + Alt + Space` anywhere in Windows (Word, Notepad, Slack, Discord, VS Code, Browser, WhatsApp).
  - Speak naturally, press `Ctrl + Alt + Space` again.
  - Text is instantly typed directly where your cursor is.

- **100% Offline & Private**:
  - Runs locally on your CPU using quantized `faster-whisper` models (`base.en`, `tiny.en`).
  - Sub-second inference time (**~0.20s**). No audio ever leaves your machine.
- **Audio & Video File Transcriber**:
  - Drag & drop local media (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.mkv`).
  - Subtitle generation and export to **TXT** or **SRT**.
- **Searchable History Studio**:
  - SQLite-backed history storing all transcripts, timestamps, and audio durations.
  - One-click copy and instant search.
- **System Tray Integration**:
  - Runs discreetly in the Windows taskbar system tray with quick-toggle and studio launcher.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10/11
- Python 3.10+ (Tested on Python 3.11)

### 2. Installation
The repository includes automated setup:
```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Install dependencies
.\.venv\Scripts\pip install -r requirements.txt
```

### 3. Launching the App
Double-click `run.bat` or run from PowerShell:
```powershell
.\.venv\Scripts\python.exe -m app.main
```

### 4. CLI Dictation Mode (Terminal Only)
If you prefer running dictation directly in your terminal:
```powershell
.\.venv\Scripts\python.exe cli.py
```

---

## ⌨️ How to Use System-Wide Dictation

1. Launch Flow STT (`run.bat` or `python -m app.main`).
2. Switch to **any application** (e.g., Notepad, VS Code, Word, Chrome).
3. Press **`Ctrl + Alt + Space`**.
4. The floating pill will appear showing `Listening...` with a dynamic waveform.
5. Speak your message, then press **`Ctrl + Alt + Space`** again.
6. The audio transcribes instantly and pastes into your focused window!

---

## 📁 Project Structure

```
flow/
├── app/
│   ├── config.py                 # Application settings & preferences
│   ├── main.py                   # Central coordinator & Qt application
│   ├── core/
│   │   ├── audio_recorder.py     # sounddevice mic stream & RMS levels
│   │   ├── stt_engine.py         # faster-whisper CTranslate2 INT8 model engine
│   │   ├── hotkey_manager.py     # pynput system-wide global hotkeys
│   │   └── text_injector.py      # Windows SendInput & clipboard auto-paster
│   ├── ui/
│   │   ├── floating_pill.py      # Translucent floating recording overlay
│   │   ├── main_window.py        # Studio dashboard (tabs, files, history)
│   │   └── tray_icon.py          # Windows taskbar system tray icon
│   └── utils/
│       └── db.py                 # SQLite local transcription history
├── models/                       # Downloaded local Whisper model weights
├── tests/
│   ├── test_components.py        # Core component verification
│   └── test_engine.py            # faster-whisper inference speed test
├── cli.py                        # Terminal dictation runner
├── requirements.txt
├── run.bat                       # One-click desktop launcher
└── README.md
```

---

## ⚙️ Configuration & Customization

Settings can be changed inside the **Settings** tab in the Studio or in `config.json`:
- `model_size`: `tiny.en` (fastest), `base.en` (recommended), `small.en` (most accurate)
- `hotkey`: Any key combination (default: `<ctrl>+<alt>+<space>`)
- `auto_paste`: `true` or `false`
- `copy_to_clipboard`: `true` or `false`
- `groq_api_key`: Optional API key for sub-second cloud transcription

---

## 🛡️ Privacy & Security
All microphone audio is recorded into memory (RAM buffer) and processed locally by the quantized model. No audio or transcriptions are uploaded to external servers unless you explicitly provide a cloud API key.
