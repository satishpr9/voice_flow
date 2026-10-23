import sys
import os
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QTabWidget, QComboBox, QCheckBox,
    QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QProgressBar, QScrollArea
)

from app.config import AppConfig
from app.utils.db import HistoryDatabase


class FileTranscriptionWorker(QThread):
    finished = Signal(list, str)
    error = Signal(str)

    def __init__(self, stt_engine, file_path: str):
        super().__init__()
        self.stt_engine = stt_engine
        self.file_path = file_path

    def run(self):
        try:
            segments = self.stt_engine.transcribe_file(self.file_path)
            full_text = " ".join(seg["text"] for seg in segments)
            self.finished.emit(segments, full_text)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window for Flow STT (Studio, File Transcriber, History, Settings)."""

    dictation_requested = Signal()

    def __init__(self, config: AppConfig, stt_engine, db: HistoryDatabase, ai_service=None):
        super().__init__()
        self.config = config
        self.stt_engine = stt_engine
        self.db = db
        self.ai_service = ai_service

        self.setWindowTitle("Flow STT - Voice Dictation & Audio Studio")
        self.resize(850, 620)
        self.setMinimumSize(700, 500)

        self._apply_dark_theme()
        self._init_ui()
        self.refresh_history()

    def _apply_dark_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #1E293B;
                background: #0F172A;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1E293B;
                color: #94A3B8;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #3B82F6;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QPushButton#secondaryBtn {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #334155;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                color: #F8FAFC;
                selection-background-color: #3B82F6;
            }
            QComboBox::drop-down {
                border: none;
            }
            QTableWidget {
                background-color: #1E293B;
                border: 1px solid #334155;
                gridline-color: #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #0F172A;
                color: #94A3B8;
                padding: 6px;
                border: 1px solid #334155;
                font-weight: 600;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                background-color: #1E293B;
                color: #F8FAFC;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 3px;
            }
            """
        )

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._build_dictation_tab()
        self._build_file_tab()
        self._build_history_tab()
        self._build_settings_tab()

    def _build_dictation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info Banner
        header = QLabel("🎙️ Voice Dictation Studio")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(header)

        info = QLabel(
            f"Press <b>{self.config.hotkey}</b> anywhere in Windows to trigger dictation.<br>"
            "Text will be automatically typed or copied to clipboard."
        )
        info.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(info)

        # Dictation output box
        self.dictation_box = QTextEdit()
        self.dictation_box.setPlaceholderText("Live dictation transcripts will appear here...")
        layout.addWidget(self.dictation_box, 1)

        # Action bar
        btn_bar = QHBoxLayout()
        self.btn_manual_record = QPushButton("● Start Recording")
        self.btn_manual_record.clicked.connect(lambda: self.dictation_requested.emit())

        btn_copy = QPushButton("Copy Text")
        btn_copy.setObjectName("secondaryBtn")
        btn_copy.clicked.connect(self._copy_dictation)

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.clicked.connect(self.dictation_box.clear)

        btn_bar.addWidget(self.btn_manual_record)
        btn_bar.addWidget(btn_copy)
        btn_bar.addWidget(btn_clear)
        btn_bar.addStretch()

        layout.addLayout(btn_bar)
        self.tabs.addTab(tab, "Dictation")

    def _build_file_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("📁 Audio & Video File Transcription")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(header)

        # File picker section
        file_select_bar = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select an audio/video file (.mp3, .wav, .m4a, .mp4)...")
        btn_browse = QPushButton("Browse...")
        btn_browse.setObjectName("secondaryBtn")
        btn_browse.clicked.connect(self._browse_audio_file)

        self.btn_transcribe_file = QPushButton("Transcribe File")
        self.btn_transcribe_file.clicked.connect(self._start_file_transcription)

        file_select_bar.addWidget(self.file_path_edit, 1)
        file_select_bar.addWidget(btn_browse)
        file_select_bar.addWidget(self.btn_transcribe_file)
        layout.addLayout(file_select_bar)

        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 0) # indeterminate
        self.file_progress.hide()
        layout.addWidget(self.file_progress)

        # File Transcript result box
        self.file_result_box = QTextEdit()
        self.file_result_box.setPlaceholderText("Transcription output will appear here...")
        layout.addWidget(self.file_result_box, 1)

        # Export options
        export_bar = QHBoxLayout()
        btn_export_txt = QPushButton("Export as TXT")
        btn_export_txt.setObjectName("secondaryBtn")
        btn_export_txt.clicked.connect(self._export_txt)

        btn_export_srt = QPushButton("Export as SRT (Subtitles)")
        btn_export_srt.setObjectName("secondaryBtn")
        btn_export_srt.clicked.connect(self._export_srt)

        export_bar.addWidget(btn_export_txt)
        export_bar.addWidget(btn_export_srt)
        export_bar.addStretch()
        layout.addLayout(export_bar)

        self.tabs.addTab(tab, "File Transcriber")
        self._last_file_segments = []

    def _build_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("📜 Transcription History")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(header)

        # Search bar
        search_bar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search past transcripts...")
        self.search_edit.textChanged.connect(self._on_search)
        btn_clear_hist = QPushButton("Clear All History")
        btn_clear_hist.setObjectName("secondaryBtn")
        btn_clear_hist.clicked.connect(self._clear_history)

        search_bar.addWidget(self.search_edit, 1)
        search_bar.addWidget(btn_clear_hist)
        layout.addLayout(search_bar)

        # History Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["ID", "Timestamp", "Duration", "Transcript"])
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.doubleClicked.connect(self._on_history_row_clicked)
        layout.addWidget(self.history_table, 1)

        self.tabs.addTab(tab, "History")

    def _build_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header = QLabel("⚙️ Preferences & Engine Settings")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(header)

        # 1. Local Whisper Model
        group_model = QGroupBox("Local Speech Engine (faster-whisper INT8)")
        model_layout = QVBoxLayout(group_model)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["tiny.en", "base.en", "small.en", "tiny", "base", "small"])
        self.combo_model.setCurrentText(self.config.model_size)
        model_layout.addWidget(QLabel("Select Local Model (base.en recommended for speed & accuracy on CPU):"))
        model_layout.addWidget(self.combo_model)
        layout.addWidget(group_model)

        # 2. Wispr Flow AI Cloud Intelligence Group
        group_ai = QGroupBox("Wispr Flow Cloud AI Intelligence (MiMo / Qwen / Groq)")
        ai_layout = QVBoxLayout(group_ai)
        ai_layout.setSpacing(10)

        self.check_ai_enabled = QCheckBox("Enable Cloud AI Intelligence (Wispr Flow Smart LLM Polish)")
        self.check_ai_enabled.setChecked(self.config.ai_enabled)
        self.check_ai_enabled.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 13px;")
        ai_layout.addWidget(self.check_ai_enabled)

        # Model selection row
        row_model = QHBoxLayout()
        row_model.addWidget(QLabel("AI Model:"))
        self.combo_ai_model = QComboBox()
        self.combo_ai_model.setEditable(True)
        model_presets = [
            "xiaomi/mimo-v2.6-flash",
            "qwen/qwen3.8-omni-flash",
            "groq/llama-3.1-8b-instant",
            "openai/gpt-4o-mini",
            "google/gemini-2.0-flash",
        ]
        if self.config.ai_model and self.config.ai_model not in model_presets:
            self.combo_ai_model.addItem(self.config.ai_model)
        for m in model_presets:
            self.combo_ai_model.addItem(m)
        self.combo_ai_model.setCurrentText(self.config.ai_model)
        row_model.addWidget(self.combo_ai_model, 1)
        ai_layout.addLayout(row_model)

        # Mode row
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Execution Mode:"))
        self.combo_ai_mode = QComboBox()
        self.combo_ai_mode.addItem("Text Polish (Whisper STT + AI LLM formatting - Fast & Snappy)")
        self.combo_ai_mode.addItem("Omni Audio (Direct Audio to Omni Multimodal Model)")
        if self.config.ai_mode == "omni_audio":
            self.combo_ai_mode.setCurrentIndex(1)
        else:
            self.combo_ai_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ai_mode, 1)
        ai_layout.addLayout(row_mode)

        # Base URL row
        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("API Base URL:"))
        self.edit_ai_base_url = QLineEdit(self.config.ai_base_url)
        self.edit_ai_base_url.setPlaceholderText("https://openrouter.ai/api/v1")
        row_url.addWidget(self.edit_ai_base_url, 1)
        ai_layout.addLayout(row_url)

        # API Key row
        row_key = QHBoxLayout()
        row_key.addWidget(QLabel("API Key:"))
        self.edit_ai_key = QLineEdit(self.config.ai_api_key)
        self.edit_ai_key.setEchoMode(QLineEdit.Password)
        self.edit_ai_key.setPlaceholderText("sk-or-v1-... or your provider key")
        row_key.addWidget(self.edit_ai_key, 1)
        ai_layout.addLayout(row_key)

        # Test Connection button & status
        test_row = QHBoxLayout()
        self.btn_test_ai = QPushButton("⚡ Test Connection")
        self.btn_test_ai.setObjectName("secondaryBtn")
        self.btn_test_ai.clicked.connect(self._test_ai_connection)
        self.lbl_test_status = QLabel("")
        self.lbl_test_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
        test_row.addWidget(self.btn_test_ai)
        test_row.addWidget(self.lbl_test_status, 1)
        ai_layout.addLayout(test_row)

        layout.addWidget(group_ai)

        # 3. Text Polish & Feedback
        group_wispr = QGroupBox("Wispr Flow Polish & Audio Feedback")
        wispr_layout = QVBoxLayout(group_wispr)

        self.check_clean_speech = QCheckBox("Wispr Flow Polish (auto-remove 'um', 'uh', stutters, fix punctuation)")
        self.check_clean_speech.setChecked(self.config.clean_speech)
        wispr_layout.addWidget(self.check_clean_speech)

        self.check_play_chimes = QCheckBox("Play subtle sound chimes on start and stop dictation")
        self.check_play_chimes.setChecked(self.config.play_chimes)
        wispr_layout.addWidget(self.check_play_chimes)

        layout.addWidget(group_wispr)

        # 4. Hotkey & Integration
        group_hotkey = QGroupBox("Dictation & Hotkey")
        hotkey_layout = QVBoxLayout(group_hotkey)

        hotkey_input_row = QHBoxLayout()
        hotkey_input_row.addWidget(QLabel("Global Hotkey:"))
        self.edit_hotkey = QLineEdit(self.config.hotkey)
        hotkey_input_row.addWidget(self.edit_hotkey, 1)
        hotkey_layout.addLayout(hotkey_input_row)

        self.check_auto_paste = QCheckBox("Auto-paste text into active window")
        self.check_auto_paste.setChecked(self.config.auto_paste)
        hotkey_layout.addWidget(self.check_auto_paste)

        self.check_clipboard = QCheckBox("Always copy transcript to clipboard")
        self.check_clipboard.setChecked(self.config.copy_to_clipboard)
        hotkey_layout.addWidget(self.check_clipboard)
        layout.addWidget(group_hotkey)

        # Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        scroll.setWidget(tab)
        self.tabs.addTab(scroll, "Settings")

    def _copy_dictation(self):
        text = self.dictation_box.toPlainText()
        if text:
            import pyperclip
            pyperclip.copy(text)
            QMessageBox.information(self, "Copied", "Transcript copied to clipboard!")

    def update_live_partial(self, partial_text: str):
        """Displays real-time live words as they are being spoken."""
        current = self.dictation_box.toPlainText()
        lines = [line for line in current.split("\n") if not line.startswith("🎙️ [Live]:")]
        base_text = "\n".join(lines).strip()
        if base_text:
            self.dictation_box.setPlainText(f"{base_text}\n\n🎙️ [Live]: {partial_text}")
        else:
            self.dictation_box.setPlainText(f"🎙️ [Live]: {partial_text}")

        # Auto-scroll to end
        cursor = self.dictation_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.dictation_box.setTextCursor(cursor)

    def append_dictation_text(self, text: str):
        current = self.dictation_box.toPlainText()
        lines = [line for line in current.split("\n") if not line.startswith("🎙️ [Live]:")]
        base_text = "\n".join(lines).strip()
        if base_text:
            self.dictation_box.setPlainText(f"{base_text}\n\n{text}")
        else:
            self.dictation_box.setPlainText(text)
        self.refresh_history()

    def _browse_audio_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video File",
            "",
            "Audio & Video Files (*.mp3 *.wav *.m4a *.mp4 *.mkv *.flac *.aac);;All Files (*.*)",
        )
        if path:
            self.file_path_edit.setText(path)

    def _start_file_transcription(self):
        path = self.file_path_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Invalid File", "Please select a valid audio or video file.")
            return

        self.file_progress.show()
        self.btn_transcribe_file.setEnabled(False)
        self.file_result_box.setPlainText("Transcribing audio file, please wait...")

        self.worker = FileTranscriptionWorker(self.stt_engine, path)
        self.worker.finished.connect(self._on_file_transcription_finished)
        self.worker.error.connect(self._on_file_transcription_error)
        self.worker.start()

    def _on_file_transcription_finished(self, segments, full_text):
        from app.core.text_cleaner import TextCleaner
        self.file_progress.hide()
        self.btn_transcribe_file.setEnabled(True)

        if self.config.clean_speech:
            if self.ai_service and self.config.ai_enabled and self.config.ai_api_key.strip():
                full_text = self.ai_service.polish_text(full_text)
            else:
                full_text = TextCleaner.clean(full_text)

        self._last_file_segments = segments
        self.file_result_box.setPlainText(full_text)

        # Save to DB
        file_name = Path(self.file_path_edit.text()).name
        self.db.save_record(
            text=full_text,
            model_used=self.config.model_size,
            source="file",
            file_name=file_name,
        )
        self.refresh_history()

    def _on_file_transcription_error(self, err_msg):
        self.file_progress.hide()
        self.btn_transcribe_file.setEnabled(True)
        QMessageBox.critical(self, "Transcription Error", f"Failed to transcribe: {err_msg}")

    def _export_txt(self):
        text = self.file_result_box.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Transcript", "transcript.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Exported", f"Saved transcript to {path}")

    def _export_srt(self):
        if not self._last_file_segments:
            QMessageBox.warning(self, "No Subtitles", "No segment data available to export as SRT.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save SRT Subtitles", "subtitles.srt", "SubRip Subtitles (*.srt)")
        if not path:
            return

        def format_time(seconds: float) -> str:
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds - int(seconds)) * 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

        with open(path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(self._last_file_segments, 1):
                f.write(f"{idx}\n")
                f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")

        QMessageBox.information(self, "Exported", f"Saved subtitles to {path}")

    def refresh_history(self, records=None):
        if records is None:
            records = self.db.get_recent(limit=100)

        self.history_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.history_table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            self.history_table.setItem(row, 1, QTableWidgetItem(rec["timestamp"]))
            self.history_table.setItem(row, 2, QTableWidgetItem(f"{rec['duration_seconds']:.1f}s"))
            self.history_table.setItem(row, 3, QTableWidgetItem(rec["text"]))

    def _on_search(self, text: str):
        if text.strip():
            records = self.db.search(text.strip())
            self.refresh_history(records)
        else:
            self.refresh_history()

    def _on_history_row_clicked(self, index):
        row = index.row()
        text_item = self.history_table.item(row, 3)
        if text_item:
            import pyperclip
            pyperclip.copy(text_item.text())
            QMessageBox.information(self, "Copied", "Copied selected transcript to clipboard!")

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History", "Are you sure you want to delete all past transcriptions?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_all()
            self.refresh_history()

    def _test_ai_connection(self):
        if not self.ai_service:
            from app.core.ai_service import AIService
            self.ai_service = AIService(self.config)

        # Update test config with current UI inputs
        test_config = AppConfig(
            ai_enabled=True,
            ai_model=self.combo_ai_model.currentText().strip(),
            ai_base_url=self.edit_ai_base_url.text().strip(),
            ai_api_key=self.edit_ai_key.text().strip(),
            ai_mode="omni_audio" if "omni" in self.combo_ai_mode.currentText().lower() else "text_polish",
        )
        self.ai_service.update_config(test_config)
        self.lbl_test_status.setText("Testing connection...")
        self.lbl_test_status.setStyleSheet("color: #FBBF24; font-size: 11px;")
        self.btn_test_ai.setEnabled(False)

        def _worker():
            success, msg = self.ai_service.test_connection()
            def _update():
                self.btn_test_ai.setEnabled(True)
                if success:
                    self.lbl_test_status.setText(f"✓ {msg}")
                    self.lbl_test_status.setStyleSheet("color: #4ADE80; font-size: 11px; font-weight: bold;")
                else:
                    self.lbl_test_status.setText(f"✗ {msg}")
                    self.lbl_test_status.setStyleSheet("color: #F87171; font-size: 11px;")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, _update)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _save_settings(self):
        self.config.model_size = self.combo_model.currentText()
        self.config.hotkey = self.edit_hotkey.text().strip()
        self.config.auto_paste = self.check_auto_paste.isChecked()
        self.config.copy_to_clipboard = self.check_clipboard.isChecked()
        self.config.clean_speech = self.check_clean_speech.isChecked()
        self.config.play_chimes = self.check_play_chimes.isChecked()

        # AI Cloud Settings
        self.config.ai_enabled = self.check_ai_enabled.isChecked()
        self.config.ai_model = self.combo_ai_model.currentText().strip()
        self.config.ai_base_url = self.edit_ai_base_url.text().strip()
        self.config.ai_api_key = self.edit_ai_key.text().strip()
        self.config.ai_mode = "omni_audio" if "omni" in self.combo_ai_mode.currentText().lower() else "text_polish"

        self.config.save()
        if self.ai_service:
            self.ai_service.update_config(self.config)

        QMessageBox.information(self, "Settings Saved", "Preferences updated successfully!")
