import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import numpy as np
from app.core.stt_engine import STTEngine

def test_engine():
    print("Testing faster-whisper loading & transcription on CPU (tiny.en)...")
    engine = STTEngine(model_size="tiny.en", device="cpu", compute_type="int8", models_dir="models")
    
    t0 = time.time()
    engine.load_model()
    print(f"Model loaded in {time.time() - t0:.2f}s")
    
    # 2 seconds of 16kHz audio (silence / low noise)
    audio = np.zeros(32000, dtype=np.float32)
    t1 = time.time()
    result = engine.transcribe_audio(audio)
    print(f"Transcription completed in {time.time() - t1:.2f}s. Result: '{result}'")
    print("Engine test PASSED!")

if __name__ == "__main__":
    test_engine()
