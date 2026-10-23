import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from app.main import FlowApp
import time

def test_flow_app_init():
    print("Testing FlowApp initialization and model warmup...")
    app = QApplication.instance() or QApplication(sys.argv)
    
    flow = FlowApp(app)
    # Warmup models
    flow.stt_engine.load_model()
    
    assert flow.stt_engine._main_model is not None
    assert flow.stt_engine._live_model is not None
    print("[SUCCESS] Both main and live streaming models loaded into RAM!")
    
    # Test live chunk transcription
    import numpy as np
    audio = (np.random.randn(16000 * 2) * 0.1).astype(np.float32)
    chunk_res = flow.stt_engine.transcribe_live_chunk(audio)
    print(f"[SUCCESS] transcribe_live_chunk executed without errors (result: '{chunk_res}')")

if __name__ == "__main__":
    test_flow_app_init()
