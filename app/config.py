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

    # Cloud STT (Optional Fallback / Fast alternative)
    groq_api_key: str = ""
    use_cloud_stt: bool = False

    @classmethod
    def load(cls, file_path: Path = CONFIG_FILE_PATH) -> "AppConfig":
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"[Config] Error loading {file_path}, using defaults: {e}")
        return cls()

    def save(self, file_path: Path = CONFIG_FILE_PATH) -> None:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving {file_path}: {e}")
