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
    QHeaderView, QMessageBox, QGroupBox, QProgressBar
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

    def __init__(self, config: AppConfig, stt_engine, db: HistoryDatabase):
        super().__init__()
        self.config = config
        self.stt_engine = stt_engine
        self.db = db

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
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header = QLabel("⚙️ Preferences & Engine Settings")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(header)

        # Model selection
        group_model = QGroupBox("Whisper Model")
        model_layout = QVBoxLayout(group_model)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["tiny.en", "base.en", "small.en", "tiny", "base", "small"])
        self.combo_model.setCurrentText(self.config.model_size)
        model_layout.addWidget(QLabel("Select Model (base.en recommended for speed & accuracy on CPU):"))
        model_layout.addWidget(self.combo_model)
        layout.addWidget(group_model)

        # Wispr Flow Intelligence Group
        group_wispr = QGroupBox("Wispr Flow AI & Audio Feedback")
        wispr_layout = QVBoxLayout(group_wispr)

        self.check_clean_speech = QCheckBox("Wispr Flow Polish (auto-remove 'um', 'uh', stutters, fix capitalization)")
        self.check_clean_speech.setChecked(self.config.clean_speech)
        wispr_layout.addWidget(self.check_clean_speech)

        self.check_play_chimes = QCheckBox("Play subtle sound chimes on start and stop dictation")
        self.check_play_chimes.setChecked(self.config.play_chimes)
        wispr_layout.addWidget(self.check_play_chimes)

        layout.addWidget(group_wispr)

        # Hotkey & Integration
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

        # Cloud API (Optional)
        group_cloud = QGroupBox("Cloud Speed-Up (Optional)")
        cloud_layout = QVBoxLayout(group_cloud)
        cloud_layout.addWidget(QLabel("Groq API Key (Optional for <0.5s cloud transcription):"))
        self.edit_groq = QLineEdit(self.config.groq_api_key)
        self.edit_groq.setEchoMode(QLineEdit.Password)
        cloud_layout.addWidget(self.edit_groq)
        layout.addWidget(group_cloud)

        # Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        self.tabs.addTab(tab, "Settings")

    def _copy_dictation(self):
        text = self.dictation_box.toPlainText()
        if text:
            import pyperclip
            pyperclip.copy(text)
            QMessageBox.information(self, "Copied", "Transcript copied to clipboard!")

    def append_dictation_text(self, text: str):
        current = self.dictation_box.toPlainText()
        if current:
            self.dictation_box.setPlainText(f"{current}\n\n{text}")
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

    def _save_settings(self):
        self.config.model_size = self.combo_model.currentText()
        self.config.hotkey = self.edit_hotkey.text().strip()
        self.config.auto_paste = self.check_auto_paste.isChecked()
        self.config.copy_to_clipboard = self.check_clipboard.isChecked()
        self.config.clean_speech = self.check_clean_speech.isChecked()
        self.config.play_chimes = self.check_play_chimes.isChecked()
        self.config.groq_api_key = self.edit_groq.text().strip()
        self.config.save()
        QMessageBox.information(self, "Settings Saved", "Preferences updated successfully!")
