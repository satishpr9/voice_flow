import threading
from typing import Callable, Optional, List, Dict
import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Handles low-latency microphone audio streaming and in-memory buffer collection."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device_index: Optional[int] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.level_callback = level_callback

        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._lock = threading.Lock()
        self._frames: List[np.ndarray] = []

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @staticmethod
    def get_input_devices() -> List[Dict]:
        """Returns a list of available audio input devices."""
        devices = sd.query_devices()
        input_devs = []
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                input_devs.append(
                    {
                        "index": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_input_channels"),
                        "default_samplerate": dev.get("default_samplerate"),
                    }
                )
        return input_devs

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Audio callback triggered by sounddevice for each chunk of incoming mic audio."""
        if status:
            # Drop/overflow warning
            pass

        if not self._is_recording:
            return

        # indata has shape (frames, channels), float32 normalized [-1.0, 1.0]
        chunk = indata[:, 0].copy()

        with self._lock:
            self._frames.append(chunk)

        # Calculate current RMS (root mean square) volume level for UI visualization
        if self.level_callback:
            rms = float(np.sqrt(np.mean(chunk**2)))
            # Normalize level approximately to [0.0, 1.0]
            normalized = min(1.0, rms * 10.0)
            try:
                self.level_callback(normalized)
            except Exception:
                pass

    def start_recording(self) -> None:
        """Starts recording audio from the microphone."""
        with self._lock:
            if self._is_recording:
                return
            self._frames = []
            self._is_recording = True

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.device_index,
            callback=self._audio_callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stops recording and returns the full audio buffer as a 1D float32 numpy array."""
        with self._lock:
            self._is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._frames:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0)
            self._frames = []
            return audio
