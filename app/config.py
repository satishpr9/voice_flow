import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional

CONFIG_FILE_PATH = Path("config.json")

@dataclass
class AppConfig:
    # Model Configuration
    model_size: str = "base.en"          # "tiny.en", "base.en", "small.en", etc.
    device: str = "cpu"                  # "cpu" or "cuda"
    compute_type: str = "int8"           # "int8" for fast CPU, "float16" for GPU
    models_dir: str = "models"           # Local folder to cache Whisper models

    # Audio Configuration
    sample_rate: int = 16000             # Whisper native rate
    channels: int = 1                    # Mono
    input_device_index: Optional[int] = None  # None for system default
    silence_threshold_energy: float = 0.005   # Basic energy threshold for speech

    # Dictation & Hotkey Configuration
    hotkey: str = "<ctrl>+<alt>+<space>" # pynput format
    hotkey_mode: str = "toggle"          # "toggle" or "push_to_talk"
    auto_paste: bool = True              # Automatically paste into active window
    copy_to_clipboard: bool = True       # Always keep in clipboard
    play_chimes: bool = True             # Audio feedback on start/stop
    clean_speech: bool = True            # Speech polish (removes fillers & stutters)

    # Cloud STT (Optional Fallback / Fast alternative)
    groq_api_key: str = ""
    use_cloud_stt: bool = False

    # AI Cloud Intelligence (OpenAI-compatible / MiMo / Qwen-Omni / Groq)
    ai_enabled: bool = False
    ai_model: str = "xiaomi/mimo-v2.6-flash"
    ai_base_url: str = "https://openrouter.ai/api/v1"
    ai_api_key: str = ""
    ai_mode: str = "text_polish" # "text_polish" (Whisper + LLM Polish) or "omni_audio" (Direct Audio Omni)

    # Personalization & App-Aware Context
    app_context_aware: bool = True       # Detect active app (Slack, VS Code, Word, etc.)
    flow_style: str = "auto"             # "auto", "prose", "bullets", "email", "code", "verbatim"
    custom_vocabulary: list = field(default_factory=list) # Custom terms, jargon, names

    # Audio Processing
    noise_suppression: bool = True        # RNNoise real-time suppression before transcription

    # Privacy & Model Security Guardrails
    strict_offline_mode: bool = False     # Enforce 100% offline, blocking all cloud requests
    prompt_injection_guard: bool = True   # Sandboxes voice input in <spoken_dictation> tags
    redact_sensitive_pii: bool = False    # Auto-redact credit cards and SSNs

    @classmethod
    def load(cls, file_path: Path = CONFIG_FILE_PATH) -> "AppConfig":
        # Load .env file if present in workspace
        env_file = Path(".env")
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip('"').strip("'")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

        cfg = cls()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"[Config] Error loading {file_path}, using defaults: {e}")

        # Check environment variables if ai_api_key is empty
        if not cfg.ai_api_key:
            env_key = (
                os.environ.get("OPENAI_API_KEY")
                or os.environ.get("FLOW_AI_API_KEY")
                or os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("GROQ_API_KEY")
                or os.environ.get("MIMO_API_KEY")
            )
            if env_key:
                cfg.ai_api_key = env_key.strip()
                cfg.ai_enabled = True

        # Check environment variables for model selection
        env_model = (
            os.environ.get("OPENAI_MODEL")
            or os.environ.get("AI_MODEL")
            or os.environ.get("MODEL")
            or os.environ.get("FLOW_AI_MODEL")
        )
        if env_model:
            cfg.ai_model = env_model.strip()

        # Check environment variables for custom base_url
        env_base = (
            os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("FLOW_AI_BASE_URL")
            or os.environ.get("BASE_URL")
            or os.environ.get("base_url")
            or os.environ.get("AI_BASE_URL")
        )
        if env_base and (cfg.ai_base_url == "https://openrouter.ai/api/v1" or not cfg.ai_base_url):
            cfg.ai_base_url = env_base.strip()

        # Enforce strict offline privacy if enabled
        if cfg.strict_offline_mode:
            cfg.ai_enabled = False
            cfg.use_cloud_stt = False

        return cfg

    def save(self, file_path: Path = CONFIG_FILE_PATH) -> None:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving {file_path}: {e}")
