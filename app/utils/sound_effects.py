import numpy as np
import sounddevice as sd
import threading


class SoundEffects:
    """Generates procedural, pleasant soft audio chimes for recording start/stop.
    Does not require any external sound files.
    """

    @staticmethod
    def _play_tone(frequencies: list[float], duration_sec: float = 0.08, sample_rate: int = 44100):
        def _task():
            try:
                t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
                wave = np.zeros_like(t)

                # Combine subtle harmonic tones with smooth exponential decay envelope
                decay = np.exp(-t * (18 / duration_sec))
                for f in frequencies:
                    wave += np.sin(2 * np.pi * f * t)

                wave = (wave / len(frequencies)) * decay * 0.15 # Keep volume gentle
                sd.play(wave.astype(np.float32), samplerate=sample_rate)
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()

    @classmethod
    def play_start(cls):
        """Soft upward chime on recording start."""
        cls._play_tone([587.33, 880.0], duration_sec=0.09) # D5 -> A5

    @classmethod
    def play_stop(cls):
        """Soft downward chime on recording stop / transcription start."""
        cls._play_tone([880.0, 659.25], duration_sec=0.07) # A5 -> E5

    @classmethod
    def play_success(cls):
        """Crisp gentle double-tap chime on paste complete."""
        cls._play_tone([1046.5, 1318.5], duration_sec=0.08) # C6 -> E6
