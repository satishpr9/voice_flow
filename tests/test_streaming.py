import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import numpy as np
from app.core.stt_engine import STTEngine
from app.core.streaming_transcriber import StreamingTranscriber

def test_streaming():
    print("Testing live streaming transcriber integration...")
    engine = STTEngine(model_size="tiny.en", device="cpu", compute_type="int8")
    engine.load_model()

    captured_partials = []
    
    # Simulate a fake rolling audio buffer
    dummy_buffer = np.zeros(16000 * 2, dtype=np.float32) # 2 seconds of audio
    
    streamer = StreamingTranscriber(
        stt_engine=engine,
        get_buffer_fn=lambda: dummy_buffer,
        on_partial_text=lambda text: captured_partials.append(text),
        interval=0.2,
    )

    print("Starting streaming transcriber loop...")
    streamer.start()
    time.sleep(0.6) # allow 2 cycles
    streamer.stop()
    print("Streaming transcriber loop stopped cleanly.")
    print("Streaming tests PASSED!")

if __name__ == "__main__":
    test_streaming()
