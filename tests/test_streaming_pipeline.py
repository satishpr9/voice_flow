import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import av
import time
import numpy as np
from faster_whisper import WhisperModel

def test_live_streaming_pipeline():
    print("Testing live streaming pipeline on JFK speech...")

    # Load audio
    container = av.open("test_jfk.flac")
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
    frames = []
    for frame in container.decode(stream):
        for r in resampler.resample(frame):
            frames.append(r.to_ndarray()[0])
    full_audio = np.concatenate(frames)

    # Initialize tiny.en live model with 2 cpu threads
    model = WhisperModel(
        "models/models--Systran--faster-whisper-tiny.en/snapshots/0d3d19a32d3338f10357c0889762bd8d64bbdeba",
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
    )

    # Simulate real-time mic streaming: feed 0.5s chunks of audio every 0.5s
    buffer = []
    chunk_size = int(0.5 * 16000) # 8000 samples per 0.5s

    for i in range(0, min(len(full_audio), 16000 * 6), chunk_size):
        chunk = full_audio[i : i + chunk_size]
        buffer.extend(chunk)

        # Transcribe the rolling window (last 3.5 seconds)
        window = np.array(buffer[-int(3.5 * 16000):], dtype=np.float32)

        t0 = time.time()
        segments, _ = model.transcribe(
            window,
            beam_size=1,
            best_of=1,
            vad_filter=False,
            without_timestamps=True,
            temperature=0.0,
        )
        texts = [s.text.strip() for s in segments if s.text.strip()]
        partial = " ".join(texts)
        latency = time.time() - t0

        elapsed_audio = len(buffer) / 16000.0
        print(f"[{elapsed_audio:4.1f}s audio] (latency: {latency:.2f}s) Live: '{partial}'")

if __name__ == "__main__":
    test_live_streaming_pipeline()
