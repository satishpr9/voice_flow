"""
Tests for Stage 2 — NoiseSuppressor (RNNoise-based)

Two public entry points, both tested:
  suppress_buffer(audio, sr)    — full recorded buffer  (TranscriptionWorker)
  suppress_frame(frame_16k)     — one sounddevice block  (AudioRecorder callback)

Coverage:
  - Silence / white-noise passthrough without crash
  - RMS reduction on white noise (neural suppressor does heavy lifting)
  - Exact length preservation after resample round-trip
  - float32 dtype preserved throughout
  - Disabled mode returns original array unchanged
  - Very short clips (<0.25 s) bypass suppression
  - Non-1D arrays returned unchanged (guard)
  - Fallback when pyrnnoise unavailable (monkeypatched)
  - reset() clears real-time state for next session
  - suppress_frame accumulates partial frames correctly
"""

import numpy as np
import pytest

from app.core.noise_suppressor import NoiseSuppressor

SAMPLE_RATE = 16000
BLOCK = 1024  # AudioRecorder blocksize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def silence(seconds: float = 1.0) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def white_noise(seconds: float = 1.0, amp: float = 0.3) -> np.ndarray:
    rng = np.random.default_rng(42)
    return (rng.standard_normal(int(SAMPLE_RATE * seconds)) * amp).astype(np.float32)


def rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(a ** 2)))


# ---------------------------------------------------------------------------
# suppress_buffer — recorded-audio path
# ---------------------------------------------------------------------------

class TestSuppressBuffer:

    def test_silence_no_crash(self):
        """A buffer of silence must not raise any exception."""
        s = NoiseSuppressor(enabled=True)
        result = s.suppress_buffer(silence(1.0), SAMPLE_RATE)
        assert result is not None
        assert len(result) > 0

    def test_white_noise_rms_reduced(self):
        """RNNoise must substantially reduce white noise RMS."""
        s = NoiseSuppressor(enabled=True)
        audio = white_noise(seconds=2.0, amp=0.3)
        clean = s.suppress_buffer(audio, SAMPLE_RATE)
        assert rms(clean) < rms(audio) * 0.5, (
            f"Expected large RMS reduction; got {rms(clean):.4f} vs {rms(audio):.4f}"
        )

    def test_length_preserved(self):
        """Output must have the same number of samples as input."""
        s = NoiseSuppressor(enabled=True)
        audio = white_noise(seconds=1.5)
        result = s.suppress_buffer(audio, SAMPLE_RATE)
        assert len(result) == len(audio), f"{len(result)} != {len(audio)}"

    def test_dtype_float32(self):
        """Output must be float32 (faster-whisper requirement)."""
        s = NoiseSuppressor(enabled=True)
        result = s.suppress_buffer(white_noise(1.0), SAMPLE_RATE)
        assert result.dtype == np.float32

    def test_disabled_returns_original(self):
        """When disabled, suppress_buffer() must return the original array."""
        s = NoiseSuppressor(enabled=False)
        audio = white_noise(1.0)
        result = s.suppress_buffer(audio, SAMPLE_RATE)
        np.testing.assert_array_equal(result, audio)

    def test_short_clip_passthrough(self):
        """Clips shorter than 0.25 s are too short — pass through unchanged."""
        s = NoiseSuppressor(enabled=True)
        short = white_noise(seconds=0.1)  # 1600 samples < 4000 threshold
        result = s.suppress_buffer(short, SAMPLE_RATE)
        np.testing.assert_array_equal(result, short)

    def test_2d_array_passthrough(self):
        """Non-1D arrays are returned unchanged (shape guard)."""
        s = NoiseSuppressor(enabled=True)
        bad = np.zeros((2, SAMPLE_RATE), dtype=np.float32)
        result = s.suppress_buffer(bad, SAMPLE_RATE)
        np.testing.assert_array_equal(result, bad)

    def test_pyrnnoise_unavailable_fallback(self, monkeypatch):
        """If pyrnnoise is absent, audio is returned unchanged without crash."""
        import app.core.noise_suppressor as ns_mod
        monkeypatch.setattr(ns_mod, "_pyrnnoise_available", False)
        s = NoiseSuppressor(enabled=True)
        audio = white_noise(1.0)
        result = s.suppress_buffer(audio, SAMPLE_RATE)
        np.testing.assert_array_equal(result, audio)


# ---------------------------------------------------------------------------
# suppress_frame — real-time callback path
# ---------------------------------------------------------------------------

class TestSuppressFrame:

    def test_single_block_no_crash(self):
        """A single 1024-sample block must not crash."""
        s = NoiseSuppressor(enabled=True)
        frame = white_noise(seconds=BLOCK / SAMPLE_RATE, amp=0.2)
        result = s.suppress_frame(frame)
        assert result is not None
        assert len(result) == len(frame)

    def test_frame_dtype_float32(self):
        """suppress_frame must return float32."""
        s = NoiseSuppressor(enabled=True)
        frame = white_noise(seconds=BLOCK / SAMPLE_RATE)
        result = s.suppress_frame(frame)
        assert result.dtype == np.float32

    def test_multiple_frames_reduce_noise(self):
        """After several frames of white noise, RNNoise should attenuate it."""
        s = NoiseSuppressor(enabled=True)
        # Feed 20 frames (~1.3 s at 16 kHz, plenty for the RNN to stabilise)
        frames_in = [white_noise(seconds=BLOCK / SAMPLE_RATE, amp=0.3) for _ in range(20)]
        frames_out = [s.suppress_frame(f) for f in frames_in]

        rms_in = rms(np.concatenate(frames_in))
        rms_out = rms(np.concatenate(frames_out))
        assert rms_out < rms_in * 0.8, (
            f"Expected frame-level RMS reduction; got {rms_out:.4f} vs {rms_in:.4f}"
        )

    def test_disabled_returns_original_frame(self):
        """When disabled, suppress_frame() must return the original frame."""
        s = NoiseSuppressor(enabled=False)
        frame = white_noise(seconds=BLOCK / SAMPLE_RATE)
        result = s.suppress_frame(frame)
        np.testing.assert_array_equal(result, frame)

    def test_reset_clears_state(self):
        """reset() must clear denoiser state so a new session starts fresh."""
        s = NoiseSuppressor(enabled=True)
        # Run some frames
        for _ in range(5):
            s.suppress_frame(white_noise(seconds=BLOCK / SAMPLE_RATE))
        # Reset and confirm the denoiser re-initialises
        s.reset()
        assert s._rt_denoiser is None
        assert len(s._rt_leftover) == 0

    def test_empty_frame_passthrough(self):
        """An empty array must be returned unchanged."""
        s = NoiseSuppressor(enabled=True)
        empty = np.empty(0, dtype=np.float32)
        result = s.suppress_frame(empty)
        np.testing.assert_array_equal(result, empty)

    def test_2d_frame_passthrough(self):
        """A 2D frame is returned unchanged (shape guard)."""
        s = NoiseSuppressor(enabled=True)
        bad = np.zeros((2, BLOCK), dtype=np.float32)
        result = s.suppress_frame(bad)
        np.testing.assert_array_equal(result, bad)
