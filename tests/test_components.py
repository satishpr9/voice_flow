import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np

def test_imports():
    print("1. Testing imports...")
    import sounddevice as sd
    import faster_whisper
    import PySide6
    import pynput
    import pyperclip
    from app.config import AppConfig
    from app.core.audio_recorder import AudioRecorder
    from app.core.stt_engine import STTEngine
    from app.core.text_injector import TextInjector
    from app.utils.db import HistoryDatabase
    print("   [SUCCESS] All core modules imported cleanly!")

def test_devices():
    print("2. Testing audio input devices...")
    from app.core.audio_recorder import AudioRecorder
    devices = AudioRecorder.get_input_devices()
    print(f"   Found {len(devices)} input device(s):")
    for d in devices[:3]:
        print(f"   - [{d['index']}] {d['name']} (Channels: {d['channels']}, Default SR: {d['default_samplerate']})")
    print("   [SUCCESS] Device enumeration works!")

def test_database():
    print("3. Testing SQLite history database...")
    from app.utils.db import HistoryDatabase
    db = HistoryDatabase()
    rec_id = db.save_record("Test speech to text transcription", duration_seconds=2.5, model_used="tiny.en")
    assert rec_id > 0
    records = db.get_recent(5)
    assert len(records) > 0
    print(f"   [SUCCESS] Database saved & retrieved test record (id={rec_id})!")

if __name__ == "__main__":
    test_imports()
    test_devices()
    test_database()
    print("\nAll component tests PASSED!")
