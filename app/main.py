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
from app.core.text_cleaner import TextCleaner
from app.core.ai_service import AIService
from app.core.streaming_transcriber import StreamingTranscriber
from app.utils.db import HistoryDatabase
from app.utils.sound_effects import SoundEffects
from app.ui.floating_pill import FloatingPill
from app.ui.main_window import MainWindow
from app.ui.tray_icon import SystemTrayManager


class TranscriptionWorker(QObject):
    finished = Signal(str, float) # transcript text, duration

    def __init__(self, stt_engine: STTEngine, ai_service: AIService, clean_speech: bool = True):
        super().__init__()
        self.stt_engine = stt_engine
        self.ai_service = ai_service
        self.clean_speech = clean_speech

    def transcribe(self, audio_data, duration: float):
        def _task():
            try:
                t0 = time.time()
                final_text = ""

                # 1. Check if Direct Omni Audio mode is configured
                if (
                    self.ai_service.config.ai_enabled
                    and self.ai_service.config.ai_mode == "omni_audio"
                    and self.ai_service.config.ai_api_key.strip()
                ):
                    omni_result = self.ai_service.transcribe_omni_audio(audio_data)
                    if omni_result:
                        final_text = omni_result

                # 2. If not omni or omni returned empty, use local STT engine
                if not final_text:
                    raw_text = self.stt_engine.transcribe_audio(audio_data)
                    if not raw_text:
                        self.finished.emit("", duration)
                        return

                    # 3. Apply AI Polish (MiMo / Qwen / Groq) or local regex TextCleaner
                    if self.clean_speech:
                        if self.ai_service.config.ai_enabled and self.ai_service.config.ai_api_key.strip():
                            final_text = self.ai_service.polish_text(raw_text)
                        else:
                            final_text = TextCleaner.clean(raw_text)
                    else:
                        final_text = raw_text

                print(f"[STT] Dictation processed in {time.time() - t0:.2f}s: '{final_text}'")
                self.finished.emit(final_text, duration)
            except Exception as e:
                print(f"[STT] Transcription error: {e}")
                self.finished.emit("", duration)

        threading.Thread(target=_task, daemon=True).start()


class FlowApp(QObject):
    """Core controller coordinating Audio, STT Engine, Hotkeys, and Wispr Flow UI."""

    toggle_requested = Signal()
    audio_level_signal = Signal(float)
    live_transcript_signal = Signal(str)

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

        # Real-time streaming transcriber (Wispr Flow live transcribing)
        self.streamer = StreamingTranscriber(
            stt_engine=self.stt_engine,
            get_buffer_fn=self.audio_recorder.get_current_buffer,
            on_partial_text=lambda partial: self.live_transcript_signal.emit(partial),
            interval=0.55,
        )

        self.ai_service = AIService(self.config)
        self.text_injector = TextInjector()
        self.worker = TranscriptionWorker(self.stt_engine, self.ai_service, clean_speech=self.config.clean_speech)
        self.worker.finished.connect(self._on_transcription_finished)

        # UI Components
        self.pill = FloatingPill()
        self.main_window = MainWindow(self.config, self.stt_engine, self.db, self.ai_service)
        self.tray = SystemTrayManager()

        # Wire Signals
        self.toggle_requested.connect(self.toggle_recording)
        self.audio_level_signal.connect(self.pill.level_updated.emit)
        self.pill.cancel_requested.connect(self._cancel_recording)

        # Wire real-time live transcribing stream
        self.live_transcript_signal.connect(self.pill.live_text_updated.emit)
        self.live_transcript_signal.connect(self.main_window.update_live_partial)

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
        self._is_cancelled = False

    def start(self):
        """Initializes services, pre-warms Whisper, and activates Wispr Flow listener."""
        print("[FlowApp] Starting Voice Flow (Wispr Flow style)...")

        # Pre-load Whisper model in background thread
        def _warmup():
            self.stt_engine.load_model()
        threading.Thread(target=_warmup, daemon=True).start()

        # Start Global Hotkey Listener
        try:
            self.hotkey_manager.start()
        except Exception as e:
            print(f"[FlowApp] Warning: Could not register global hotkey: {e}")

        # Show Studio Window
        self.main_window.show()

        # Show tray balloon notification
        self.tray.show_message(
            "Voice Flow Ready",
            f"Press {self.config.hotkey} anywhere to dictate."
        )

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
        self._is_cancelled = False
        print("[FlowApp] Recording started...")
        self._record_start_time = time.time()

        if self.config.play_chimes:
            SoundEffects.play_start()

        self.audio_recorder.start_recording()
        self.streamer.start()
        self.pill.set_recording()
        self.main_window.btn_manual_record.setText("■ Stop Recording")

    def _cancel_recording(self):
        """User pressed cancel ✕ on the floating pill."""
        print("[FlowApp] Recording cancelled by user.")
        self._is_cancelled = True
        self.streamer.stop()
        self.audio_recorder.stop_recording()
        self.pill.set_idle()
        self.main_window.btn_manual_record.setText("● Start Recording")

    def _stop_recording(self):
        if self._is_cancelled:
            return

        duration = time.time() - self._record_start_time
        print(f"[FlowApp] Recording stopped (duration: {duration:.2f}s). Processing...")

        # Stop streaming loop before final transcription
        self.streamer.stop()

        if self.config.play_chimes:
            SoundEffects.play_stop()

        self.pill.set_processing()
        self.main_window.btn_manual_record.setText("● Start Recording")

        audio_data = self.audio_recorder.stop_recording()
        if len(audio_data) == 0:
            self.pill.set_idle()
            return

        # Hand off to transcription worker thread
        self.worker.clean_speech = self.config.clean_speech
        self.worker.transcribe(audio_data, duration)

    @Slot(str, float)
    def _on_transcription_finished(self, text: str, duration: float):
        if not text:
            print("[FlowApp] No speech detected.")
            self.pill.set_idle()
            return

        # Save to local SQLite history
        self.db.save_record(
            text=text,
            duration_seconds=duration,
            model_used=self.config.model_size,
            source="dictation",
        )

        # Update Main Window Dictation Studio
        self.main_window.append_dictation_text(text)

        # Show success state on pill
        success_label = "Pasted!" if self.config.auto_paste else "Copied!"
        self.pill.set_success(success_label)

        if self.config.play_chimes:
            SoundEffects.play_success()

        # Inject into active window cursor or copy to clipboard
        if self.config.auto_paste:
            # Short 60ms delay ensures previous window maintains input focus
            QTimer.singleShot(60, lambda: self.text_injector.paste_text(text))
        elif self.config.copy_to_clipboard:
            import pyperclip
            pyperclip.copy(text)

    def quit_app(self):
        print("[FlowApp] Shutting down...")
        self.streamer.stop()
        self.hotkey_manager.stop()
        self.audio_recorder.stop_recording()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    flow = FlowApp(app)
    flow.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
