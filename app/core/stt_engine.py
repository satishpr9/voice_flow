import os
import time
import threading
from typing import Optional, List, Dict
from pathlib import Path
import numpy as np

# Suppress Hugging Face Windows symlink warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class STTEngine:
    """Manages local Whisper models for both real-time streaming and high-accuracy final transcription."""

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        models_dir: str = "models",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._main_model: Optional[WhisperModel] = None
        self._live_model: Optional[WhisperModel] = None
        self._lock = threading.Lock()

    def load_model(self) -> None:
        """Pre-loads both the main model and the ultra-fast live streaming model."""
        with self._lock:
            if self._main_model is None:
                print(f"[STTEngine] Loading main model '{self.model_size}'...")
                t0 = time.time()
                self._main_model = WhisperModel(
                    model_size_or_path=self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=str(self.models_dir),
                    cpu_threads=2,
                )
                print(f"[STTEngine] Main model loaded in {time.time() - t0:.2f}s.")

            if self._live_model is None:
                # Always use tiny.en for sub-400ms real-time live transcribing
                print("[STTEngine] Loading real-time live streaming model 'tiny.en'...")
                t1 = time.time()
                self._live_model = WhisperModel(
                    model_size_or_path="tiny.en",
                    device=self.device,
                    compute_type="int8",
                    download_root=str(self.models_dir),
                    cpu_threads=2,
                )
                print(f"[STTEngine] Live model loaded in {time.time() - t1:.2f}s.")

    def transcribe_live_chunk(self, audio: np.ndarray) -> str:
        """Ultra-fast (sub-400ms) live streaming partial transcription."""
        if audio is None or len(audio) < 6400: # at least 0.4s
            return ""

        # Check volume energy - skip pure silence to preserve CPU
        rms = float(np.sqrt(np.mean(audio[-8000:]**2))) if len(audio) >= 8000 else float(np.sqrt(np.mean(audio**2)))
        if rms < 0.0025:
            return ""

        if self._live_model is None:
            self.load_model()

        # Limit window to the last 12 seconds max for instant responsiveness
        max_samples = 16000 * 12
        audio_slice = audio[-max_samples:] if len(audio) > max_samples else audio

        try:
            # Fast greedy pass with no VAD filter (so live words are not dropped)
            segments, _ = self._live_model.transcribe(
                audio_slice,
                language="en",
                beam_size=1,
                best_of=1,
                vad_filter=False, # CRITICAL: False allows continuous live words
                without_timestamps=True,
                temperature=0.0,
            )
            texts = [seg.text.strip() for seg in segments if seg.text.strip()]
            return " ".join(texts).strip()
        except Exception as e:
            print(f"[STTEngine] Live chunk error: {e}")
            return ""

    def transcribe_audio(
        self,
        audio: np.ndarray,
        language: Optional[str] = "en",
        vad_filter: bool = True,
    ) -> str:
        """High-accuracy final transcription executed upon stopping dictation."""
        if audio is None or len(audio) == 0:
            return ""

        if self._main_model is None:
            self.load_model()

        segments, info = self._main_model.transcribe(
            audio,
            language=language,
            beam_size=1,
            best_of=1,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=350),
            condition_on_previous_text=False,
        )

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts).strip()

    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        vad_filter: bool = True,
    ) -> List[Dict]:
        """Transcribes an audio or video file with timestamps."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if self._main_model is None:
            self.load_model()

        segments, info = self._main_model.transcribe(
            file_path,
            language=language,
            beam_size=5,
            vad_filter=vad_filter,
        )

        results = []
        for seg in segments:
            results.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                }
            )
        return results
