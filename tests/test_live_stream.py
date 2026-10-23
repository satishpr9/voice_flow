import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import av
import numpy as np
import time
from app.core.stt_engine import STTEngine

def test_jfk_stream():
    container = av.open("test_jfk.flac")
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)

    frames = []
    for frame in container.decode(stream):
        for r_frame in resampler.resample(frame):
            frames.append(r_frame.to_ndarray()[0])
    audio = np.concatenate(frames)
    print(f"Loaded JFK audio: {len(audio)} samples ({len(audio)/16000:.2f}s)")

    eng = STTEngine(model_size="tiny.en", device="cpu", compute_type="int8")
    eng.load_model()

    for sec in [1.0, 2.0, 3.0, 4.0, 5.0]:
        slice_audio = audio[:int(sec * 16000)]
        t0 = time.time()
        text = eng.transcribe_live_chunk(slice_audio)
        elapsed = time.time() - t0
        print(f"At {sec}s (took {elapsed:.2f}s): '{text}'")

if __name__ == "__main__":
    test_jfk_stream()
