import time
import threading
from typing import Callable, Optional
import numpy as np


class StreamingTranscriber:
    """Runs low-latency background transcription loops while recording,
    emitting live text updates as words are spoken in real-time.
    """

    def __init__(
        self,
        stt_engine,
        get_buffer_fn: Callable[[], np.ndarray],
        on_partial_text: Callable[[str], None],
        interval: float = 0.35,
    ):
        self.stt_engine = stt_engine
        self.get_buffer_fn = get_buffer_fn
        self.on_partial_text = on_partial_text
        self.interval = interval

        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._last_emitted = ""

    def start(self):
        """Starts real-time live transcribing loop."""
        if self._is_running:
            return
        self._is_running = True
        self._last_emitted = ""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops real-time live transcribing loop."""
        self._is_running = False
        if self._thread is not None:
            self._thread = None

    def _loop(self):
        # Allow initial buffer accumulation (~0.4s)
        time.sleep(0.35)

        while self._is_running:
            try:
                audio_buffer = self.get_buffer_fn()

                # Need at least 0.4s of audio (6400 samples @ 16kHz)
                if len(audio_buffer) >= 6400 and self._is_running:
                    partial_text = self.stt_engine.transcribe_live_chunk(audio_buffer)
                    if partial_text and partial_text != self._last_emitted and self._is_running:
                        self._last_emitted = partial_text
                        try:
                            print(f"[Live] {partial_text}")
                        except Exception:
                            pass
                        self.on_partial_text(partial_text)
            except Exception as e:
                print(f"[StreamingTranscriber] Loop error: {e}")

            time.sleep(self.interval)
