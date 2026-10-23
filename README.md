# Voice Flow (Flow STT)

A high-performance, privacy-first Speech-to-Text (STT) desktop dictation application for Windows. Built with **PySide6 (Qt6)**, **faster-whisper (CTranslate2 INT8)**, Mozilla **RNNoise** neural noise suppression, and OpenAI-compatible AI intelligence.

Designed with a clean, human-crafted dark aesthetic (`#101010` / `#FFFFFF`), zero UI clutter, and strict credential isolation.

---

## 5-Stage Dictation Pipeline

Voice Flow operates on an explicit, low-latency 5-stage pipeline:

```
┌─────────────────┐
│ 1. Capture      │  Microphone stream (16 kHz float32 mono) via sounddevice
└────────┬────────┘
         │
┌────────▼────────┐
│ 2. Suppress     │  Mozilla RNNoise neural noise suppression (shared real-time & batch)
└────────┬────────┘
         │
┌────────▼────────┐
│ 3. Transcribe   │  faster-whisper (offline INT8) or OpenAI-compatible Cloud STT / Omni
└────────┬────────┘
         │
┌────────▼────────┐
│ 4. Polish       │  Remove fillers/stutters, fix punctuation (Local Regex or Sandboxed LLM)
└────────┬────────┘
         │
┌────────▼────────┐
│ 5. Insert       │  Instant paste into active Windows foreground application
└─────────────────┘
```

### Stage 1: Audio Capture
- **Engine**: `AudioRecorder` utilizing `sounddevice` with an uncompressed circular buffer.
- **Specification**: 16,000 Hz, 1-channel mono, 32-bit floating point PCM.
- **Audio Feedback**: Live RMS calculation driving real-time UI waveform feedback and procedurally synthesized start/stop chimes.

### Stage 2: Real-Time & Recorded Noise Suppression
- **Engine**: `NoiseSuppressor` wrapping Mozilla's **RNNoise** recurrent neural network (via `pyrnnoise`).
- **Unified Architecture**: A single module serves both audio pathways:
  - **Streaming Callback (`suppress_frame`)**: Runs frame-by-frame on incoming 1024-sample audio blocks (~64 ms). The recurrent state persists across blocks, ensuring live streaming transcripts receive clean, hiss-free audio.
  - **Full Buffer (`suppress_buffer`)**: Applied on recorded audio batches before transcription.
- **Internal Processing**: Automatic polyphase resampling (16 kHz $\leftrightarrow$ 48 kHz exact $\times 3 / \div 3$) and int16 conversion.
- **Session Isolation**: `reset()` automatically clears the RNN memory bank on every recording start.
- **Resilient Fallback**: Gracefully passes through original audio if dependencies are missing or processing encounters an issue.

### Stage 3: Speech-to-Text Transcription
- **Local Engine (Default)**: `faster-whisper` powered by quantized CTranslate2 INT8 models (`base.en`, `tiny.en`, `small.en`). Fully offline, running on CPU with sub-second latency (~0.2s).
- **Live Streaming**: `StreamingTranscriber` generates rolling partial transcripts every 0.55s while speaking.
- **Cloud STT / Omni Audio**: Supports OpenAI-compatible multimodal audio endpoints for direct speech-to-text inference.

### Stage 4: Transcript Polish
- **Local Mode (Default)**: `TextCleaner` uses zero-latency regex rules to eliminate verbal filler words (*"um"*, *"uh"*, *"you know"*, *"like"*), clean speech stutters (*"I I went"* $\rightarrow$ *"I went"*), and normalize punctuation/capitalization.
- **Cloud AI Polish**: Sends raw transcripts to any OpenAI-compatible LLM (e.g., MiMo, Groq, OpenRouter, local Ollama) for context-aware prose formatting, markdown conversion, or email structuring.
- **Sandboxed Security**: Prompts are strictly quarantined within `<spoken_dictation>` tags to defend against prompt injection attacks.

### Stage 5: System-Wide Active Application Insertion
- **Engine**: `TextInjector` and `WindowContextDetector`.
- **Insertion**: High-speed clipboard injection combined with simulated Windows keystroke events (`Ctrl + V`). Focus remains undisturbed in the target application.
- **App Context Awareness**: Detects active applications (VS Code, Slack, Word, Terminal, Browser) and tailors formatting style automatically.

---

## Clean, Human-Crafted UI

The interface is intentionally designed without AI gimmicks, rainbow gradients, or clutter:

- **Monochrome Dark Palette**: Background `#101010`, surface cards `#181818`, clean `#FFFFFF` typography.
- **Standard Medium Typography**: Readable 14px interface fonts with strict typographic hierarchy.
- **Physical Keycap Badges**: Hotkeys are displayed as clean physical keycaps (e.g., `[ Ctrl ] + [ Alt ] + [ Space ]`) with curated dropdown presets.
- **Floating Stay-On-Top Capsule**: Minimal pill overlay featuring 60 FPS animated audio waveform bars, live speech duration timer, active application badge, and one-click cancel (`✕`).
- **No Credentials in GUI**: API keys, endpoints, and model identifiers are strictly barred from the UI. Configuration occurs exclusively through environment variables and local `.env` files.

---

## 🔒 Security & Privacy

Detailed security architecture and audit results are documented in [security.md](file:///d:/flow/security.md).

- **Credential Isolation**: No sensitive API keys or model names are exposed in user interface windows or settings dialogs.
- **Log Sanitization**: Automated regex scrubbers strip `sk-...` API tokens and secrets from all log files and error traces.
- **PII Auto-Redaction**: Optional automated masking for sensitive user information (credit card numbers and Social Security numbers).
- **Prompt Injection Sandboxing**: User dictation is encapsulated in delimited XML tags with explicit system instructions to ignore embedded control directives.
- **Strict Offline Mode**: Toggleable hard offline mode that disables cloud endpoints and guarantees zero network traffic.

---

## Quick Start

### 1. Requirements
- Windows 10 or 11 (64-bit)
- Python 3.10+ (Tested on Python 3.11)

### 2. Installation
Clone the repository and install dependencies inside a virtual environment:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration (.env)
Create a `.env` file in the project root to configure cloud LLM polish or multimodal STT (optional):

```ini
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=xiaomi/mimo-v2.6-flash
```

> **Note**: If `.env` is omitted, Voice Flow defaults to 100% offline local transcription and local regex text cleaning.

### 4. Running the Application

**Desktop GUI Application:**
```powershell
.\.venv\Scripts\python.exe -m app.main
```
*Or double-click `run.bat`.*

**Terminal CLI Mode:**
```powershell
.\.venv\Scripts\python.exe cli.py
```

---

## How to Dictate

1. Start Voice Flow. The discreet floating pill appears on screen.
2. Focus any Windows program (Notepad, Word, VS Code, Discord, Slack, Browser).
3. Press **`Ctrl + Alt + Space`** (or your customized hotkey).
4. Speak naturally. The pill visualizes your audio waveform and streams partial text.
5. Press **`Ctrl + Alt + Space`** again (or release in Push-to-Talk mode).
6. The audio is denoised with RNNoise, transcribed, polished, and immediately typed at your cursor.

---

## Project Structure

```
flow/
├── app/
│   ├── config.py                 # Configuration dataclass & .env loader
│   ├── main.py                   # Main Qt application & 5-stage coordinator
│   ├── core/
│   │   ├── audio_recorder.py     # sounddevice input stream & RMS monitoring
│   │   ├── noise_suppressor.py   # Mozilla RNNoise (real-time frame & batch)
│   │   ├── stt_engine.py         # faster-whisper CTranslate2 INT8 engine
│   │   ├── streaming_transcriber.py # Background thread for live chunk streaming
│   │   ├── ai_service.py         # OpenAI-compatible API client & security guards
│   │   ├── text_cleaner.py       # Local regex filler & stutter cleaner
│   │   ├── hotkey_manager.py     # Global hotkey listener (Toggle & Push-to-Talk)
│   │   └── text_injector.py      # Low-latency clipboard & keystroke auto-paste
│   ├── ui/
│   │   ├── floating_pill.py      # Floating capsule with live waveform & timer
│   │   ├── main_window.py        # Clean dark-and-white studio dashboard
│   │   └── tray_icon.py          # Windows notification area system tray integration
│   └── utils/
│       ├── db.py                 # SQLite local transcription history database
│       ├── sound_effects.py      # Procedural sound feedback synthesis
│       └── window_context.py     # Windows active window & process detector
├── models/                       # Local cached faster-whisper model weights
├── tests/                        # Comprehensive automated test suite
│   ├── test_noise_suppressor.py  # RNNoise frame & buffer verification (15 tests)
│   ├── test_cleaner.py           # TextCleaner speech normalization tests
│   ├── test_ui_security.py       # UI credential hiding verification
│   ├── test_model_security.py    # Sandboxing, PII masking, offline guards
│   ├── test_api_key_checks.py    # API authorization & URL normalization
│   └── test_hotkey_manager.py    # Key combination parsing & translation
├── cli.py                        # Terminal-based standalone dictation runner
├── requirements.txt              # Production dependency specifications
├── security.md                   # Full security audit & vulnerability report
├── run.bat                       # Quick launcher script for Windows
└── README.md
```

---

## Testing

Execute the test suite using `pytest`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

To run headless UI and security tests without opening visible windows:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m pytest tests/test_ui_security.py -v
```

---

## License

Private and proprietary. Designed for personal and local productivity workflows.
