import sys
import time
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.core.audio_recorder import AudioRecorder
from app.core.stt_engine import STTEngine
from app.core.text_injector import TextInjector
from app.core.hotkey_manager import HotkeyManager
from app.utils.db import HistoryDatabase
from app.ui.floating_pill import FloatingPill
from app.ui.main_window import MainWindow
from app.ui.tray_icon import SystemTrayManager


class TranscriptionWorker(QObject):
    finished = Signal(str, float) # transcript text, duration

    def __init__(self, stt_engine: STTEngine):
        super().__init__()
        self.stt_engine = stt_engine

    def transcribe(self, audio_data, duration: float):
        def _task():
            try:
                t0 = time.time()
                text = self.stt_engine.transcribe_audio(audio_data)
                print(f"[STT] Transcribed in {time.time() - t0:.2f}s: '{text}'")
                self.finished.emit(text, duration)
            except Exception as e:
                print(f"[STT] Transcription error: {e}")
                self.finished.emit("", duration)

        threading.Thread(target=_task, daemon=True).start()


class FlowApp(QObject):
    """Core controller coordinating Audio, STT Engine, Hotkeys, and UI."""

    # Thread-safe signals to communicate from background threads to Qt UI
    toggle_requested = Signal()
    audio_level_signal = Signal(float)

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app

        # Load Config & Database
        self.config = AppConfig.load()
        self.db = HistoryDatabase()

        # Core Services
        self.stt_engine = STTEngine(
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            models_dir=self.config.models_dir,
        )

        self.audio_recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            device_index=self.config.input_device_index,
            level_callback=lambda lvl: self.audio_level_signal.emit(lvl),
        )

        self.text_injector = TextInjector()
        self.worker = TranscriptionWorker(self.stt_engine)
        self.worker.finished.connect(self._on_transcription_finished)

        # UI Components
        self.pill = FloatingPill()
        self.main_window = MainWindow(self.config, self.stt_engine, self.db)
        self.tray = SystemTrayManager()

        # Connect UI and Controller Signals
        self.toggle_requested.connect(self.toggle_recording)
        self.audio_level_signal.connect(self.pill.level_updated.emit)

        self.main_window.dictation_requested.connect(self.toggle_recording)
        self.tray.show_studio_requested.connect(self._show_studio)
        self.tray.toggle_dictation_requested.connect(self.toggle_recording)
        self.tray.quit_requested.connect(self.quit_app)

        # Hotkey Manager
        self.hotkey_manager = HotkeyManager(
            hotkey_str=self.config.hotkey,
            on_toggle=lambda: self.toggle_requested.emit(),
            mode=self.config.hotkey_mode,
        )

        self._record_start_time = 0.0

    def start(self):
        """Initializes services, pre-warms the STT engine, and shows UI."""
        print("[FlowApp] Starting Flow STT application...")

        # Pre-load Whisper model in background thread so first dictation is instant
        def _warmup():
            self.stt_engine.load_model()
        threading.Thread(target=_warmup, daemon=True).start()

        # Start Global Hotkey Listener
        try:
            self.hotkey_manager.start()
        except Exception as e:
            print(f"[FlowApp] Warning: Could not register global hotkey: {e}")

        # Show main studio window
        self.main_window.show()

    def _show_studio(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @Slot()
    def toggle_recording(self):
        if not self.audio_recorder.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        print("[FlowApp] Recording started...")
        self._record_start_time = time.time()
        self.audio_recorder.start_recording()
        self.pill.set_recording_state(True)
        self.main_window.btn_manual_record.setText("■ Stop Recording")

    def _stop_recording(self):
        duration = time.time() - self._record_start_time
        print(f"[FlowApp] Recording stopped (duration: {duration:.2f}s). Processing...")
        self.pill.set_recording_state(False)
        self.main_window.btn_manual_record.setText("● Start Recording")

        audio_data = self.audio_recorder.stop_recording()
        if len(audio_data) == 0:
            self.pill.hide()
            return

        # Hand off to transcription worker thread
        self.worker.transcribe(audio_data, duration)

    @Slot(str, float)
    def _on_transcription_finished(self, text: str, duration: float):
        self.pill.hide()

        if not text:
            print("[FlowApp] No speech detected.")
            return

        # Save to local SQLite database
        self.db.save_record(
            text=text,
            duration_seconds=duration,
            model_used=self.config.model_size,
            source="dictation",
        )

        # Update Main Window Dictation Studio
        self.main_window.append_dictation_text(text)

        # Inject into active window or clipboard
        if self.config.auto_paste:
            # Short delay to ensure focus is restored to previous window
            QTimer.singleShot(80, lambda: self.text_injector.paste_text(text))
        elif self.config.copy_to_clipboard:
            import pyperclip
            pyperclip.copy(text)

    def quit_app(self):
        print("[FlowApp] Shutting down...")
        self.hotkey_manager.stop()
        self.audio_recorder.stop_recording()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Keep running in system tray

    flow = FlowApp(app)
    flow.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
