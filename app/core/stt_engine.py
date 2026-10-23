import os
import time
from typing import Optional, List, Dict, Generator
from pathlib import Path
import numpy as np

# Suppress Hugging Face Windows symlink warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class STTEngine:
    """Manages local Whisper model lifecycle and audio transcription."""

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

        self._model: Optional[WhisperModel] = None
        self._is_loading = False

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        """Loads or downloads the Whisper model into RAM."""
        if self._model is not None:
            return

        self._is_loading = True
        print(f"[STTEngine] Loading model '{self.model_size}' (device={self.device}, compute_type={self.compute_type})...")
        t0 = time.time()

        self._model = WhisperModel(
            model_size_or_path=self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(self.models_dir),
            cpu_threads=4,
        )
        self._is_loading = False
        print(f"[STTEngine] Model loaded in {time.time() - t0:.2f} seconds.")

    def transcribe_audio(
        self,
        audio: np.ndarray,
        language: Optional[str] = "en",
        vad_filter: bool = True,
    ) -> str:
        """Transcribes a 1D float32 numpy audio buffer (sampled at 16000Hz).
        Returns the combined transcribed text.
        """
        if audio is None or len(audio) == 0:
            return ""

        # Make sure model is ready
        if self._model is None:
            self.load_model()

        # Run transcription with built-in Silero VAD to strip leading/trailing silence
        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=1,            # 1 = greedy (fastest for real-time dictation)
            best_of=1,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=400),
            condition_on_previous_text=False,
        )

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        result = " ".join(texts).strip()
        return result

    def transcribe_live_chunk(
        self,
        audio: np.ndarray,
        language: Optional[str] = "en",
    ) -> str:
        """Fast low-latency inference for live real-time partial streaming."""
        if audio is None or len(audio) < 8000: # at least 0.5s of audio
            return ""

        if self._model is None:
            self.load_model()

        # Limit window to recent 10 seconds for real-time responsiveness
        max_samples = 16000 * 10
        audio_slice = audio[-max_samples:] if len(audio) > max_samples else audio

        segments, _ = self._model.transcribe(
            audio_slice,
            language=language,
            beam_size=1,
            best_of=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=250),
            condition_on_previous_text=False,
            without_timestamps=True,
        )

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts).strip()

    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None,
        vad_filter: bool = True,
    ) -> List[Dict]:
        """Transcribes an audio or video file, returning detailed segments with timestamps."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if self._model is None:
            self.load_model()

        segments, info = self._model.transcribe(
            file_path,
            language=language,
            beam_size=5,            # Higher beam size for files to maximize accuracy
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
