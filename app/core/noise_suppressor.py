"""
Stage 2 — RNNoise-based Noise Suppressor
=========================================
Wraps Mozilla's RNNoise recurrent-neural-network noise suppressor (via pyrnnoise)
and exposes a single interface used by both audio paths:

  suppress_buffer(audio, sr)  — full recorded buffer  (TranscriptionWorker)
  suppress_frame(frame_16k)   — one 1024-sample chunk  (AudioRecorder callback)

Audio contract throughout the app:
  • 16 kHz mono float32 in the range [-1.0, 1.0]

RNNoise contract:
  • 48 kHz mono int16, processed in 480-sample frames (10 ms each)

This module handles all resampling and dtype conversion internally so that
callers never have to think about it.

Fallback:  if pyrnnoise is not importable or suppression fails, the original
           audio is returned unchanged — the pipeline is never interrupted.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RNNoise constants — kept in sync with pyrnnoise internals
# ---------------------------------------------------------------------------
_RNNOISE_RATE: int = 48000       # RNNoise native sample rate
_RNNOISE_FRAME: int = 480        # samples per 10 ms frame at 48 kHz

# Resample ratios for 16 kHz ↔ 48 kHz  (exact: ×3 / ÷3)
_UP: int = 3
_DOWN: int = 1

# ---------------------------------------------------------------------------
# Lazy import cache
# ---------------------------------------------------------------------------
_pyrnnoise_available: Optional[bool] = None


def _check_pyrnnoise() -> bool:
    global _pyrnnoise_available
    if _pyrnnoise_available is None:
        try:
            import pyrnnoise  # noqa: F401
            _pyrnnoise_available = True
        except ImportError:
            _pyrnnoise_available = False
            logger.warning(
                "[NoiseSuppressor] 'pyrnnoise' not installed — noise suppression disabled. "
                "Install with: pip install pyrnnoise"
            )
    return _pyrnnoise_available


# ---------------------------------------------------------------------------
# Helper: resample float32 between 16 kHz and 48 kHz via scipy polyphase
# ---------------------------------------------------------------------------

def _to_48k(audio_16k: np.ndarray) -> np.ndarray:
    from scipy.signal import resample_poly
    return resample_poly(audio_16k, _UP, _DOWN).astype(np.float32)


def _to_16k(audio_48k: np.ndarray) -> np.ndarray:
    from scipy.signal import resample_poly
    return resample_poly(audio_48k, _DOWN, _UP).astype(np.float32)


# ---------------------------------------------------------------------------
# Helper: float32 [-1,1] ↔ int16
# ---------------------------------------------------------------------------

def _f32_to_i16(audio: np.ndarray) -> np.ndarray:
    return (audio * 32767.0).clip(-32768, 32767).astype(np.int16)


def _i16_to_f32(audio: np.ndarray) -> np.ndarray:
    return audio.astype(np.float32) / 32767.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class NoiseSuppressor:
    """
    RNNoise-based noise suppressor shared by the recorded-audio path and the
    real-time streaming path.

    Thread-safety:
        suppress_buffer() creates a fresh RNNoise state each call — safe for
        concurrent use from different threads.

        suppress_frame() keeps persistent RNNoise state between frames so that
        the recurrent network's memory spans an entire dictation session.  It is
        NOT thread-safe to call suppress_frame() from multiple threads
        simultaneously; use a separate NoiseSuppressor instance per thread.
    """

    def __init__(self, enabled: bool = True) -> None:
        """
        Args:
            enabled:  Master toggle. When False, both paths are no-ops.
        """
        self.enabled = enabled

        # Persistent state for the frame-by-frame streaming path
        self._rt_denoiser = None       # pyrnnoise.RNNoise instance, lazy-created
        self._rt_lock = threading.Lock()
        self._rt_leftover: np.ndarray = np.empty(0, dtype=np.float32)  # partial frame buffer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def suppress_buffer(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Denoise a complete recorded-audio buffer.

        Used by:  TranscriptionWorker.transcribe()

        Args:
            audio:        float32 ndarray, shape (N,), mono 16 kHz
            sample_rate:  must be 16000 (reserved for future flexibility)

        Returns:
            Denoised float32 ndarray of the same length, or original on failure.
        """
        if not self.enabled or not _check_pyrnnoise():
            return audio

        if not _is_valid_buffer(audio):
            return audio

        try:
            import pyrnnoise

            # Upsample to 48 kHz int16
            audio_48k_i16 = _f32_to_i16(_to_48k(audio))

            # pyrnnoise expects shape [channels, samples]
            chunk_2d = audio_48k_i16[np.newaxis, :]

            # Fresh denoiser per call — no shared state between recordings
            denoiser = pyrnnoise.RNNoise(sample_rate=_RNNOISE_RATE)
            frames = list(denoiser.denoise_chunk(chunk_2d, partial=True))

            if not frames:
                return audio

            denoised_48k_i16 = np.concatenate([f[1] for f in frames], axis=1).squeeze()

            # Downsample back to 16 kHz float32
            result = _to_16k(_i16_to_f32(denoised_48k_i16))

            # Trim/pad to exact input length (resampler may produce ±1 sample)
            result = _match_length(result, len(audio))

            rms_in = float(np.sqrt(np.mean(audio ** 2)))
            rms_out = float(np.sqrt(np.mean(result ** 2)))
            logger.debug(
                "[NoiseSuppressor] buffer RMS %.4f → %.4f (%.1f%% reduction)",
                rms_in, rms_out,
                (1 - rms_out / rms_in) * 100 if rms_in > 1e-9 else 0.0,
            )
            return result

        except Exception as exc:
            logger.warning("[NoiseSuppressor] suppress_buffer failed (%s) — using original audio.", exc)
            return audio

    def suppress_frame(self, frame_16k: np.ndarray) -> np.ndarray:
        """
        Denoise a single chunk of audio from the microphone callback in real time.

        Used by:  AudioRecorder._audio_callback() — called every ~64 ms
                  (blocksize=1024 samples @ 16 kHz)

        The method is stateful: the RNNoise recurrent net retains memory across
        consecutive calls within one recording session.  Call reset() when a
        new dictation session starts.

        Args:
            frame_16k:  float32 ndarray, shape (N,) — one sounddevice block

        Returns:
            Denoised float32 ndarray of the same length, or original on failure.
        """
        if not self.enabled or not _check_pyrnnoise():
            return frame_16k

        if frame_16k.ndim != 1 or len(frame_16k) == 0:
            return frame_16k

        try:
            import pyrnnoise

            with self._rt_lock:
                # Lazy-create the persistent denoiser
                if self._rt_denoiser is None:
                    self._rt_denoiser = pyrnnoise.RNNoise(sample_rate=_RNNOISE_RATE)

                # Convert incoming 16 kHz float32 → 48 kHz int16
                frame_48k_i16 = _f32_to_i16(_to_48k(frame_16k))  # shape: (N*3,)

                # Accumulate with any leftover from the previous call
                combined = np.concatenate([self._rt_leftover, frame_48k_i16])

                # RNNoise frame size at 48 kHz
                frame_size = _RNNOISE_FRAME  # 480 samples = 10 ms

                n_frames = len(combined) // frame_size
                if n_frames == 0:
                    # Not enough samples yet — hold and return original
                    self._rt_leftover = combined
                    return frame_16k

                usable = combined[: n_frames * frame_size]
                self._rt_leftover = combined[n_frames * frame_size :]

                # Process usable frames through RNNoise
                chunk_2d = usable[np.newaxis, :]  # shape (1, n_frames*480)
                results = list(
                    self._rt_denoiser.denoise_chunk(chunk_2d, partial=False)
                )

                if not results:
                    return frame_16k

                denoised_48k_i16 = np.concatenate([r[1] for r in results], axis=1).squeeze()

                # Convert back: 48 kHz int16 → 16 kHz float32
                result = _to_16k(_i16_to_f32(denoised_48k_i16))
                result = _match_length(result, len(frame_16k))
                return result

        except Exception as exc:
            logger.warning("[NoiseSuppressor] suppress_frame failed (%s) — using original frame.", exc)
            return frame_16k

    def reset(self) -> None:
        """
        Reset the real-time denoiser state between dictation sessions.
        Call this when a new recording starts so the RNN's memory is clean.
        """
        with self._rt_lock:
            self._rt_denoiser = None
            self._rt_leftover = np.empty(0, dtype=np.float32)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_valid_buffer(audio: np.ndarray) -> bool:
    """Return True only for mono float32 arrays long enough to process."""
    if not isinstance(audio, np.ndarray):
        return False
    if audio.ndim != 1:
        logger.debug("[NoiseSuppressor] Skipping non-1D audio (shape=%s).", audio.shape)
        return False
    min_samples = 16000 // 4  # 0.25 s minimum
    if len(audio) < min_samples:
        logger.debug("[NoiseSuppressor] Clip too short (%d samples) — skipping.", len(audio))
        return False
    return True


def _match_length(audio: np.ndarray, target_len: int) -> np.ndarray:
    """Trim or zero-pad to exactly target_len samples."""
    if len(audio) >= target_len:
        return audio[:target_len]
    return np.pad(audio, (0, target_len - len(audio)))
