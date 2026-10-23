import av
import numpy as np
import time
from pathlib import Path
from faster_whisper import WhisperModel

def main():
    flac_path = Path(__file__).resolve().parent.parent / "test_jfk.flac"
    if not flac_path.exists():
        print(f"Skipping test_full_buffer: {flac_path} does not exist.")
        return

    container = av.open(str(flac_path))
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
    frames = [r.to_ndarray()[0] for f in container.decode(stream) for r in resampler.resample(f)]
    audio = np.concatenate(frames)

    model = WhisperModel(
        "models/models--Systran--faster-whisper-tiny.en/snapshots/0d3d19a32d3338f10357c0889762bd8d64bbdeba",
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
    )

    for sec in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]:
        t0 = time.time()
        segments, _ = model.transcribe(
            audio[:int(sec * 16000)],
            beam_size=1,
            best_of=1,
            vad_filter=False,
            without_timestamps=True,
            temperature=0.0,
        )
        texts = [s.text.strip() for s in segments]
        print(f"Full {sec:4.1f}s audio took {time.time()-t0:.2f}s: '{' '.join(texts)}'")

if __name__ == "__main__":
    main()
