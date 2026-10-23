import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import av
import time
import numpy as np
from app.core.stt_engine import STTEngine
from app.core.streaming_transcriber import StreamingTranscriber

def test_end_to_end():
    print("Testing End-to-End Live Streaming...")
    
    # Load test audio
    container = av.open("test_jfk.flac")
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
    frames = [r.to_ndarray()[0] for f in container.decode(stream) for r in resampler.resample(f)]
    audio_full = np.concatenate(frames)

    # Initialize Engine with dual models
    engine = STTEngine(model_size="base.en")
    engine.load_model()

    # Shared buffer simulating live mic buffer
    live_buffer = []
    emitted_texts = []

    def get_buf():
        return np.array(live_buffer, dtype=np.float32)

    def on_live(text):
        emitted_texts.append(text)
        print(f"  [LIVE UI EMIT]: '{text}'")

    streamer = StreamingTranscriber(
        stt_engine=engine,
        get_buffer_fn=get_buf,
        on_partial_text=on_live,
        interval=0.35,
    )
    
    streamer.start()

    # Simulate speaking 4 seconds of audio in 0.2s slices
    step = int(0.2 * 16000)
    for i in range(0, int(4.0 * 16000), step):
        live_buffer.extend(audio_full[i : i + step])
        time.sleep(0.2)

    streamer.stop()

    print(f"\nTotal live partial updates emitted: {len(emitted_texts)}")
    assert len(emitted_texts) > 0, "No live updates were emitted!"
    print("End-to-End Live Streaming test PASSED!")

if __name__ == "__main__":
    test_end_to_end()
