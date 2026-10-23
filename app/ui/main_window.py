import sys
import os
from pathlib import Path
from typing import Optional, Callable, List

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QStackedWidget, QComboBox, QCheckBox,
    QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QProgressBar, QScrollArea,
    QFrame, QButtonGroup, QGridLayout, QSizePolicy
)

from app.config import AppConfig
from app.utils.db import HistoryDatabase
from app.core.audio_recorder import AudioRecorder


def hotkey_to_display(raw: str) -> str:
    """Converts a hotkey string like '<ctrl>+<alt>+<space>' to readable 'Ctrl + Alt + Space'."""
    if not raw:
        return "Ctrl + Alt + Space"
    clean = raw.replace("<", "").replace(">", "").strip()
    parts = [p.strip().capitalize() for p in clean.split("+") if p.strip()]
    return " + ".join(parts)


def display_to_pynput(display: str) -> str:
    """Converts readable 'Ctrl + Alt + Space' to pynput format '<ctrl>+<alt>+<space>'."""
    if not display:
        return "<ctrl>+<alt>+<space>"
    s = display.strip()
    if "<" in s:
        return s
    parts = [p.strip().lower() for p in s.split("+") if p.strip()]
    return "+".join(f"<{p}>" for p in parts)


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


class PersonaCard(QFrame):
    """Clean, human-designed style card for dictation formatting."""

    clicked = Signal(str)

    def __init__(self, key: str, title: str, description: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.key = key
        self.title_text = title
        self.desc_text = description
        self.is_selected = selected

        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._init_ui()
        self._update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        self.lbl_title = QLabel(self.title_text)
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        header_row.addWidget(self.lbl_title)
        header_row.addStretch()

        self.lbl_check = QLabel("Active")
        self.lbl_check.setStyleSheet("background: #ffffff; color: #000000; font-weight: 600; font-size: 11px; padding: 2px 7px; border-radius: 4px;")
        self.lbl_check.setVisible(self.is_selected)
        header_row.addWidget(self.lbl_check)
        layout.addLayout(header_row)

        self.lbl_desc = QLabel(self.desc_text)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #a3a3a3; font-size: 13px; line-height: 1.4;")
        layout.addWidget(self.lbl_desc)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.lbl_check.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet(
                """
                PersonaCard {
                    background-color: #202020;
                    border: 1.5px solid #ffffff;
                    border-radius: 8px;
                }
                """
            )
            self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        else:
            self.setStyleSheet(
                """
                PersonaCard {
                    background-color: #171717;
                    border: 1px solid #282828;
                    border-radius: 8px;
                }
                PersonaCard:hover {
                    border-color: #444444;
                    background-color: #1c1c1c;
                }
                """
            )
            self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #e5e5e5;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
            event.accept()


class MainWindow(QMainWindow):
    """Human-crafted desktop studio for Voice Flow STT.
    Simple, clean dark background with crisp white typography and medium readable font sizing.
    """

    dictation_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        stt_engine,
        db: HistoryDatabase,
        ai_service=None,
        hotkey_manager=None,
    ):
        super().__init__()
        self.config = config
        self.stt_engine = stt_engine
        self.db = db
        self.ai_service = ai_service
        self.hotkey_manager = hotkey_manager

        self.setWindowTitle("Voice Flow")
        self.resize(1000, 680)
        self.setMinimumSize(880, 580)

        self._persona_cards = {}
        self._nav_buttons = []
        self._last_file_segments = []

        self._apply_theme()
        self._init_ui()
        self.refresh_history()

    def _apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget#rootWidget {
                background-color: #101010;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI Variable Text', 'Segoe UI', Inter, sans-serif;
                font-size: 14px;
            }

            /* Sidebar */
            QWidget#sidebar {
                background-color: #141414;
                border-right: 1px solid #222222;
            }

            QPushButton.navBtn {
                background-color: transparent;
                color: #888888;
                text-align: left;
                padding: 11px 16px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton.navBtn:hover {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton.navBtn#activeNav {
                background-color: #242424;
                color: #ffffff;
                font-weight: 600;
            }

            /* Clean Cards */
            QFrame.glassCard, QFrame.contentCard {
                background-color: #181818;
                border: 1px solid #262626;
                border-radius: 8px;
            }

            /* Inputs & Textareas */
            QLineEdit, QTextEdit, QComboBox {
                background-color: #141414;
                border: 1px solid #2c2c2c;
                border-radius: 6px;
                padding: 10px 14px;
                color: #ffffff;
                font-size: 14px;
                selection-background-color: #333333;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #ffffff;
                background-color: #171717;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #181818;
                border: 1px solid #333333;
                selection-background-color: #282828;
                color: #ffffff;
                padding: 6px;
                font-size: 14px;
            }

            /* Buttons */
            QPushButton#primaryActionBtn {
                background-color: #ffffff;
                color: #000000;
                border: none;
                padding: 10px 22px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton#primaryActionBtn:hover {
                background-color: #e5e5e5;
            }
            QPushButton#primaryActionBtn:pressed {
                background-color: #cccccc;
            }

            QPushButton.secondaryBtn, QPushButton#secondaryBtn {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #303030;
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton.secondaryBtn:hover, QPushButton#secondaryBtn:hover {
                background-color: #262626;
                border-color: #4a4a4a;
            }
            QPushButton.secondaryBtn:pressed, QPushButton#secondaryBtn:pressed {
                background-color: #1a1a1a;
            }

            QPushButton.dangerBtn {
                background-color: transparent;
                color: #ff6b6b;
                border: 1px solid #3d2020;
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton.dangerBtn:hover {
                background-color: #261414;
                color: #f87171;
                border-color: #552525;
            }

            /* Checkboxes */
            QCheckBox {
                spacing: 10px;
                color: #e0e0e0;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #383838;
                background-color: #161616;
            }
            QCheckBox::indicator:hover {
                border-color: #666666;
            }
            QCheckBox::indicator:checked {
                background-color: #ffffff;
                border-color: #ffffff;
            }

            /* Table */
            QTableWidget {
                background-color: #141414;
                border: 1px solid #242424;
                gridline-color: #1c1c1c;
                border-radius: 6px;
                color: #ffffff;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 12px 14px;
                border-bottom: 1px solid #1c1c1c;
            }
            QTableWidget::item:selected {
                background-color: #222222;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #181818;
                color: #888888;
                padding: 10px 14px;
                border: none;
                border-bottom: 1px solid #242424;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            /* Progress Bar */
            QProgressBar {
                border: 1px solid #282828;
                border-radius: 4px;
                text-align: center;
                background-color: #161616;
                color: #ffffff;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 3px;
            }

            /* Scrollbar */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a2a;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #404040;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

    def _init_ui(self):
        root = QWidget()
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Navigation Sidebar
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        # 2. Main Content Stack
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(18)

        # Top Bar
        top_bar = self._build_top_bar()
        content_layout.addLayout(top_bar)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_studio_view())      # Page 0: Dictate
        self.stack.addWidget(self._build_file_view())        # Page 1: Transcribe
        self.stack.addWidget(self._build_history_view())     # Page 2: History
        self.stack.addWidget(self._build_settings_view())    # Page 3: Settings

        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content_container, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(6)

        # Brand Header
        brand_box = QVBoxLayout()
        brand_box.setSpacing(3)
        brand_title = QLabel("Flow")
        brand_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff; letter-spacing: -0.3px;")
        brand_sub = QLabel("Speech Studio")
        brand_sub.setStyleSheet("font-size: 12px; color: #777777;")
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)
        layout.addSpacing(20)

        # Nav Buttons
        nav_items = [
            ("Dictate", 0),
            ("Transcribe", 1),
            ("History", 2),
            ("Settings", 3),
        ]

        self._nav_buttons = []
        for name, idx in nav_items:
            btn = QPushButton(name)
            btn.setProperty("class", "navBtn")
            btn.setCheckable(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx, t=name: self._switch_nav(i, t))
            if idx == 0:
                btn.setObjectName("activeNav")
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # Status footer
        status_box = QVBoxLayout()
        status_box.setSpacing(5)

        row_status = QHBoxLayout()
        self.dot_status = QLabel("●")
        self.dot_status.setStyleSheet("color: #ffffff; font-size: 10px;")
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #aaaaaa; font-size: 13px; font-weight: 500;")
        row_status.addWidget(self.dot_status)
        row_status.addWidget(self.lbl_status)
        row_status.addStretch()
        status_box.addLayout(row_status)

        readable_hotkey = hotkey_to_display(self.config.hotkey)
        self.lbl_sidebar_shortcut = QLabel(readable_hotkey)
        self.lbl_sidebar_shortcut.setStyleSheet("color: #777777; font-size: 12px;")
        status_box.addWidget(self.lbl_sidebar_shortcut)

        layout.addLayout(status_box)
        return sidebar

    def _build_top_bar(self) -> QHBoxLayout:
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 8)

        self.lbl_view_title = QLabel("Dictate")
        self.lbl_view_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        top_bar.addWidget(self.lbl_view_title)
        top_bar.addStretch()

        readable_hotkey = hotkey_to_display(self.config.hotkey)
        self.pill_hotkey = QLabel(readable_hotkey)
        self.pill_hotkey.setStyleSheet("background: #181818; border: 1px solid #282828; color: #ffffff; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 500;")
        top_bar.addWidget(self.pill_hotkey)

        mode_label = "Push-to-Talk" if self.config.hotkey_mode == "push_to_talk" else "Toggle"
        self.pill_mode = QLabel(f"Mode: {mode_label}")
        self.pill_mode.setStyleSheet("background: #181818; border: 1px solid #282828; color: #aaaaaa; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 500;")
        top_bar.addWidget(self.pill_mode)

        ai_badge = "AI Polish: Active" if (self.config.ai_enabled and not getattr(self.config, "strict_offline_mode", False)) else "AI: Offline"
        self.pill_model = QLabel(ai_badge)
        self.pill_model.setStyleSheet("background: #181818; border: 1px solid #282828; color: #ffffff; border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 500;")
        top_bar.addWidget(self.pill_model)

        return top_bar

    def _switch_nav(self, index: int, title: str):
        self.stack.setCurrentIndex(index)
        self.lbl_view_title.setText(title)
        self._highlight_nav(index)

    def _highlight_nav(self, active_index: int):
        for idx, btn in enumerate(self._nav_buttons):
            if idx == active_index:
                btn.setObjectName("activeNav")
            else:
                btn.setObjectName("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # -------------------------------------------------------------
    # Page 0: Dictation Workspace
    # -------------------------------------------------------------
    def _build_studio_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Guidance banner
        banner = QFrame()
        banner.setProperty("class", "glassCard")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(18, 12, 18, 12)
        readable_hotkey = hotkey_to_display(self.config.hotkey)
        self.lbl_banner_hint = QLabel(
            f"Press <b>{readable_hotkey}</b> anywhere in Windows to dictate directly to your active cursor."
        )
        self.lbl_banner_hint.setStyleSheet("color: #a3a3a3; font-size: 14px;")
        b_layout.addWidget(self.lbl_banner_hint)
        layout.addWidget(banner)

        # Main dictation editor card
        card = QFrame()
        card.setProperty("class", "glassCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(14)

        self.dictation_box = QTextEdit()
        self.dictation_box.setStyleSheet("font-size: 15px; line-height: 1.5;")
        self.dictation_box.setPlaceholderText(
            "Click Start Recording or press your shortcut to dictate...\n\n"
            "Words transcribe live and format automatically."
        )
        self.dictation_box.textChanged.connect(self._update_word_count)
        c_layout.addWidget(self.dictation_box, 1)

        # Bottom toolbar
        act_row = QHBoxLayout()
        self.lbl_word_count = QLabel("0 words  •  0 characters")
        self.lbl_word_count.setStyleSheet("color: #888888; font-size: 13px;")
        act_row.addWidget(self.lbl_word_count)
        act_row.addStretch()

        self.btn_manual_record = QPushButton("● Start Recording")
        self.btn_manual_record.setObjectName("primaryActionBtn")
        self.btn_manual_record.clicked.connect(lambda: self.dictation_requested.emit())
        act_row.addWidget(self.btn_manual_record)

        btn_copy = QPushButton("Copy")
        btn_copy.setObjectName("secondaryBtn")
        btn_copy.clicked.connect(self._copy_dictation)
        act_row.addWidget(btn_copy)

        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "dangerBtn")
        btn_clear.clicked.connect(self.dictation_box.clear)
        act_row.addWidget(btn_clear)

        c_layout.addLayout(act_row)
        layout.addWidget(card, 1)
        return page

    def _update_word_count(self):
        text = self.dictation_box.toPlainText()
        clean = "\n".join(l for l in text.split("\n") if not l.startswith("[Live]:")).strip()
        words = len(clean.split()) if clean else 0
        chars = len(clean)
        self.lbl_word_count.setText(f"{words} words  •  {chars} characters")

    # -------------------------------------------------------------
    # Page 1: File Transcriber
    # -------------------------------------------------------------
    def _build_file_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "glassCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(14)

        header = QLabel("Audio & Video Transcription")
        header.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        c_layout.addWidget(header)

        desc = QLabel("Select an audio or video file to transcribe locally:")
        desc.setStyleSheet("color: #a3a3a3; font-size: 13px;")
        c_layout.addWidget(desc)

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select audio or video file...")
        btn_browse = QPushButton("Browse")
        btn_browse.setObjectName("secondaryBtn")
        btn_browse.clicked.connect(self._browse_audio_file)
        file_row.addWidget(self.file_path_edit, 1)
        file_row.addWidget(btn_browse)
        c_layout.addLayout(file_row)

        self.btn_transcribe_file = QPushButton("Transcribe File")
        self.btn_transcribe_file.setObjectName("primaryActionBtn")
        self.btn_transcribe_file.clicked.connect(self._start_file_transcription)
        c_layout.addWidget(self.btn_transcribe_file)

        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 0)
        self.file_progress.setFixedHeight(4)
        self.file_progress.setTextVisible(False)
        self.file_progress.hide()
        c_layout.addWidget(self.file_progress)

        self.file_result_box = QTextEdit()
        self.file_result_box.setPlaceholderText("Transcript will appear here...")
        c_layout.addWidget(self.file_result_box, 1)

        exp_row = QHBoxLayout()
        exp_row.addStretch()

        btn_copy_file = QPushButton("Copy")
        btn_copy_file.setObjectName("secondaryBtn")
        btn_copy_file.clicked.connect(lambda: self._copy_generic(self.file_result_box.toPlainText()))
        exp_row.addWidget(btn_copy_file)

        btn_export_txt = QPushButton("Export TXT")
        btn_export_txt.setObjectName("secondaryBtn")
        btn_export_txt.clicked.connect(self._export_txt)
        exp_row.addWidget(btn_export_txt)

        btn_export_srt = QPushButton("Export SRT")
        btn_export_srt.setObjectName("secondaryBtn")
        btn_export_srt.clicked.connect(self._export_srt)
        exp_row.addWidget(btn_export_srt)

        c_layout.addLayout(exp_row)
        layout.addWidget(card, 1)
        return page

    # -------------------------------------------------------------
    # Page 2: Transcription History
    # -------------------------------------------------------------
    def _build_history_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "glassCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(14)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search past transcriptions...")
        self.search_edit.textChanged.connect(self._on_search)

        btn_clear_hist = QPushButton("Clear History")
        btn_clear_hist.setProperty("class", "dangerBtn")
        btn_clear_hist.clicked.connect(self._clear_history)

        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(btn_clear_hist)
        c_layout.addLayout(search_row)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["ID", "TIMESTAMP", "DURATION", "TRANSCRIPT"])
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.doubleClicked.connect(self._on_history_row_clicked)
        c_layout.addWidget(self.history_table, 1)

        hint = QLabel("Double-click any row to copy the transcript to clipboard.")
        hint.setStyleSheet("color: #777777; font-size: 13px;")
        c_layout.addWidget(hint)

        layout.addWidget(card, 1)
        return page

    # -------------------------------------------------------------
    # Page 3: Consolidated Settings
    # -------------------------------------------------------------
    def _build_settings_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Section 1: Shortcuts & Dictation
        hk_card = QFrame()
        hk_card.setProperty("class", "glassCard")
        hk_layout = QVBoxLayout(hk_card)
        hk_layout.setContentsMargins(20, 18, 20, 18)
        hk_layout.setSpacing(14)

        hk_header = QLabel("Keyboard Shortcut & Dictation")
        hk_header.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        hk_layout.addWidget(hk_header)

        # Visual Keyboard Keycaps row
        row_keycaps = QHBoxLayout()
        row_keycaps.setSpacing(6)
        lbl_key_title = QLabel("Shortcut:")
        lbl_key_title.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: 500;")
        row_keycaps.addWidget(lbl_key_title)

        self.keycaps_container = QHBoxLayout()
        self.keycaps_container.setSpacing(6)
        row_keycaps.addLayout(self.keycaps_container)
        row_keycaps.addStretch()
        hk_layout.addLayout(row_keycaps)

        # Shortcut Preset selector
        row_preset = QHBoxLayout()
        row_preset.addWidget(QLabel("Change shortcut:"))
        self.combo_hotkey_preset = QComboBox()
        self.combo_hotkey_preset.addItem("Ctrl + Alt + Space (Default)", "<ctrl>+<alt>+<space>")
        self.combo_hotkey_preset.addItem("Ctrl + Space", "<ctrl>+<space>")
        self.combo_hotkey_preset.addItem("Alt + Space", "<alt>+<space>")
        self.combo_hotkey_preset.addItem("Ctrl + Shift + D", "<ctrl>+<shift>+d")
        self.combo_hotkey_preset.addItem("F8", "<f8>")
        self.combo_hotkey_preset.addItem("F9", "<f9>")
        self.combo_hotkey_preset.addItem("Custom shortcut...", "custom")
        self.combo_hotkey_preset.currentIndexChanged.connect(self._on_hotkey_preset_changed)
        row_preset.addWidget(self.combo_hotkey_preset, 1)
        hk_layout.addLayout(row_preset)

        # Hidden or custom input for edit_hotkey
        self.edit_hotkey = QLineEdit(self.config.hotkey)
        self.edit_hotkey.setPlaceholderText("e.g. Ctrl + Space or <ctrl>+<alt>+<space>")
        self.edit_hotkey.textChanged.connect(self._on_custom_hotkey_typed)
        self.edit_hotkey.hide()  # Shown only when 'Custom shortcut...' is picked
        hk_layout.addWidget(self.edit_hotkey)

        # Initialize keycaps display
        self._refresh_keycaps(self.config.hotkey)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Dictation Mode:"))
        self.combo_hotkey_mode = QComboBox()
        self.combo_hotkey_mode.addItem("Toggle (press once to start, press to stop)", "toggle")
        self.combo_hotkey_mode.addItem("Push-to-Talk (hold to speak, release to paste)", "push_to_talk")
        self.combo_hotkey_mode.setCurrentIndex(1 if self.config.hotkey_mode == "push_to_talk" else 0)
        row_mode.addWidget(self.combo_hotkey_mode, 1)
        hk_layout.addLayout(row_mode)

        self.check_auto_paste = QCheckBox("Auto-paste text directly into active application")
        self.check_auto_paste.setChecked(self.config.auto_paste)
        hk_layout.addWidget(self.check_auto_paste)

        self.check_clipboard = QCheckBox("Keep transcript copied to Windows clipboard")
        self.check_clipboard.setChecked(self.config.copy_to_clipboard)
        hk_layout.addWidget(self.check_clipboard)

        self.check_play_chimes = QCheckBox("Play sound when dictation starts and stops")
        self.check_play_chimes.setChecked(self.config.play_chimes)
        hk_layout.addWidget(self.check_play_chimes)

        layout.addWidget(hk_card)

        # Section 2: Audio & Speech Engine
        loc_card = QFrame()
        loc_card.setProperty("class", "glassCard")
        l_layout = QVBoxLayout(loc_card)
        l_layout.setContentsMargins(20, 18, 20, 18)
        l_layout.setSpacing(14)

        l_header = QLabel("Audio Input & Local Speech Engine")
        l_header.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        l_layout.addWidget(l_header)

        row_mic = QHBoxLayout()
        row_mic.addWidget(QLabel("Microphone:"))
        self.combo_mic = QComboBox()
        self.combo_mic.addItem("Default System Microphone", None)
        try:
            devices = AudioRecorder.get_input_devices()
            for dev in devices:
                label = f"{dev['name']} ({dev['channels']} ch)"
                self.combo_mic.addItem(label, dev["index"])
                if self.config.input_device_index == dev["index"]:
                    self.combo_mic.setCurrentIndex(self.combo_mic.count() - 1)
        except Exception:
            pass
        row_mic.addWidget(self.combo_mic, 1)
        l_layout.addLayout(row_mic)

        row_model = QHBoxLayout()
        row_model.addWidget(QLabel("Speech Model:"))
        self.combo_local_model = QComboBox()
        self.combo_local_model.addItems(["base.en", "small.en", "tiny.en", "base", "small"])
        self.combo_local_model.setCurrentText(self.config.model_size)
        row_model.addWidget(self.combo_local_model, 1)
        l_layout.addLayout(row_model)

        self.check_app_context = QCheckBox("Format text based on active app (Slack, VS Code, Email, Browser)")
        self.check_app_context.setChecked(self.config.app_context_aware)
        l_layout.addWidget(self.check_app_context)

        layout.addWidget(loc_card)

        # Section 3: Writing Style & Custom Vocabulary
        style_card = QFrame()
        style_card.setProperty("class", "glassCard")
        s_layout = QVBoxLayout(style_card)
        s_layout.setContentsMargins(20, 18, 20, 18)
        s_layout.setSpacing(14)

        s_header = QLabel("Writing Style & Formatting")
        s_header.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        s_layout.addWidget(s_header)

        self.check_clean_speech = QCheckBox("Clean speech (removes 'um', 'uh', and verbal stutters)")
        self.check_clean_speech.setChecked(self.config.clean_speech)
        s_layout.addWidget(self.check_clean_speech)

        p_desc = QLabel("Formatting style:")
        p_desc.setStyleSheet("color: #a3a3a3; font-size: 13px;")
        s_layout.addWidget(p_desc)

        grid = QGridLayout()
        grid.setSpacing(10)

        personas = [
            ("auto", "Auto (Context Aware)", "Adapts formatting based on current application (Slack, VS Code, Email)"),
            ("prose", "Polished Prose", "Refines spoken thoughts into clear, natural written sentences"),
            ("bullets", "Bullet Points", "Converts spoken thoughts into clean markdown bullet lists"),
            ("email", "Professional Email", "Structures email correspondence with greeting and paragraphs"),
            ("code", "Code & Technical", "Preserves camelCase, snake_case identifiers and syntax"),
            ("verbatim", "Verbatim", "Exact transcription without changing words"),
        ]

        self._persona_cards = {}
        for idx, (key, title, desc_text) in enumerate(personas):
            is_sel = (self.config.flow_style == key)
            card_widget = PersonaCard(key, title, desc_text, selected=is_sel)
            card_widget.clicked.connect(self._select_persona)
            self._persona_cards[key] = card_widget
            r, c = divmod(idx, 2)
            grid.addWidget(card_widget, r, c)

        s_layout.addLayout(grid)

        row_vocab = QVBoxLayout()
        row_vocab.setSpacing(6)
        v_label = QLabel("Personal vocabulary & jargon:")
        v_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        row_vocab.addWidget(v_label)
        self.edit_vocabulary = QLineEdit(", ".join(self.config.custom_vocabulary))
        self.edit_vocabulary.setPlaceholderText("Names, technical acronyms, or company terms (comma-separated)")
        row_vocab.addWidget(self.edit_vocabulary)
        s_layout.addLayout(row_vocab)

        layout.addWidget(style_card)

        # Section 4: Privacy & Cloud AI
        sec_card = QFrame()
        sec_card.setProperty("class", "glassCard")
        sec_layout = QVBoxLayout(sec_card)
        sec_layout.setContentsMargins(20, 18, 20, 18)
        sec_layout.setSpacing(14)

        sec_header = QLabel("Privacy & Security")
        sec_header.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        sec_layout.addWidget(sec_header)

        self.check_strict_offline = QCheckBox("Offline mode (never send audio or text to the internet)")
        self.check_strict_offline.setChecked(getattr(self.config, "strict_offline_mode", False))
        self.check_strict_offline.toggled.connect(self._on_strict_offline_toggled)
        sec_layout.addWidget(self.check_strict_offline)

        self.check_ai_enabled = QCheckBox("Enable cloud AI polish (OpenAI-compatible backend)")
        self.check_ai_enabled.setChecked(self.config.ai_enabled)
        sec_layout.addWidget(self.check_ai_enabled)

        self.check_prompt_guard = QCheckBox("Prompt safety guard (prevents dictation instructions from hijacking)")
        self.check_prompt_guard.setChecked(getattr(self.config, "prompt_injection_guard", True))
        sec_layout.addWidget(self.check_prompt_guard)

        self.check_pii_redact = QCheckBox("Hide sensitive info (auto-masks credit cards & SSNs)")
        self.check_pii_redact.setChecked(getattr(self.config, "redact_sensitive_pii", False))
        sec_layout.addWidget(self.check_pii_redact)

        # Diagnostics row
        test_row = QHBoxLayout()
        self.btn_test_ai = QPushButton("Test Connection")
        self.btn_test_ai.setObjectName("secondaryBtn")
        self.btn_test_ai.clicked.connect(self._test_ai_connection)
        self.lbl_test_status = QLabel("")
        self.lbl_test_status.setStyleSheet("color: #888888; font-size: 13px;")
        test_row.addWidget(self.btn_test_ai)
        test_row.addWidget(self.lbl_test_status, 1)
        sec_layout.addLayout(test_row)

        layout.addWidget(sec_card)

        # Save Button
        btn_save = QPushButton("Save Preferences")
        btn_save.setObjectName("primaryActionBtn")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()

        if getattr(self.config, "strict_offline_mode", False):
            self._on_strict_offline_toggled(True)

        scroll.setWidget(page)
        return scroll

    def _refresh_keycaps(self, raw_hotkey: str):
        """Renders clean physical chiclet keyboard key badges."""
        # Clear existing keycaps
        while self.keycaps_container.count():
            item = self.keycaps_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        readable = hotkey_to_display(raw_hotkey)
        parts = [p.strip() for p in readable.split("+") if p.strip()]

        for i, key_name in enumerate(parts):
            cap = QLabel(key_name)
            cap.setStyleSheet(
                "background: #202020; border: 1px solid #383838; border-bottom: 2px solid #555555; "
                "border-radius: 5px; padding: 5px 12px; font-weight: 600; font-size: 13px; color: #ffffff;"
            )
            self.keycaps_container.addWidget(cap)

            if i < len(parts) - 1:
                plus = QLabel("+")
                plus.setStyleSheet("color: #777777; font-weight: bold; font-size: 14px;")
                self.keycaps_container.addWidget(plus)

    def _on_hotkey_preset_changed(self, idx: int):
        val = self.combo_hotkey_preset.currentData()
        if val == "custom":
            self.edit_hotkey.show()
        else:
            self.edit_hotkey.hide()
            self.edit_hotkey.setText(val)
            self._refresh_keycaps(val)

    def _on_custom_hotkey_typed(self, text: str):
        pynput_key = display_to_pynput(text)
        self._refresh_keycaps(pynput_key)

    def _select_persona(self, key: str):
        self.config.flow_style = key
        for k, card in self._persona_cards.items():
            card.set_selected(k == key)

    def _on_strict_offline_toggled(self, checked: bool):
        if checked:
            self.check_ai_enabled.setChecked(False)
            self.check_ai_enabled.setEnabled(False)
            self.btn_test_ai.setEnabled(False)
            self.lbl_test_status.setText("Offline mode active: cloud requests disabled.")
            self.lbl_test_status.setStyleSheet("color: #888888; font-size: 13px;")
        else:
            self.check_ai_enabled.setEnabled(True)
            self.btn_test_ai.setEnabled(True)
            self.lbl_test_status.setText("")

    # -------------------------------------------------------------
    # Shared Actions & Data Handling
    # -------------------------------------------------------------
    def _copy_dictation(self):
        text = self.dictation_box.toPlainText()
        if text:
            import pyperclip
            pyperclip.copy(text)
            QMessageBox.information(self, "Copied", "Transcript copied to clipboard.")

    def _copy_generic(self, text: str):
        if text:
            import pyperclip
            pyperclip.copy(text)
            QMessageBox.information(self, "Copied", "Copied to clipboard.")

    def update_live_partial(self, partial_text: str):
        """Displays real-time live words as they are being spoken."""
        current = self.dictation_box.toPlainText()
        lines = [line for line in current.split("\n") if not line.startswith("[Live]:") and not line.startswith("🎙️ [Live]:")]
        base_text = "\n".join(lines).strip()
        if base_text:
            self.dictation_box.setPlainText(f"{base_text}\n\n[Live]: {partial_text}")
        else:
            self.dictation_box.setPlainText(f"[Live]: {partial_text}")

        cursor = self.dictation_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.dictation_box.setTextCursor(cursor)

    def append_dictation_text(self, text: str):
        current = self.dictation_box.toPlainText()
        lines = [line for line in current.split("\n") if not line.startswith("[Live]:") and not line.startswith("🎙️ [Live]:")]
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
                full_text = self.ai_service.polish_text(
                    full_text,
                    style=self.config.flow_style,
                    custom_vocabulary=self.config.custom_vocabulary,
                )
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
            QMessageBox.information(self, "Copied", "Copied selected transcript to clipboard.")

    def _clear_history(self):
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all past transcriptions?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.clear_all()
            self.refresh_history()

    def _test_ai_connection(self):
        if getattr(self.config, "strict_offline_mode", False) or self.check_strict_offline.isChecked():
            self.lbl_test_status.setText("Offline mode active: cloud testing disabled.")
            self.lbl_test_status.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            return

        if not self.config.ai_api_key.strip():
            self.lbl_test_status.setText("No API key detected in .env or environment.")
            self.lbl_test_status.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            return

        if not self.ai_service:
            from app.core.ai_service import AIService
            self.ai_service = AIService(self.config)

        self.lbl_test_status.setText("Testing connection...")
        self.lbl_test_status.setStyleSheet("color: #e5e5e5; font-size: 13px;")
        self.btn_test_ai.setEnabled(False)

        def _worker():
            success, msg = self.ai_service.test_connection()
            def _update():
                self.btn_test_ai.setEnabled(True)
                if success:
                    self.lbl_test_status.setText("Connected successfully.")
                    self.lbl_test_status.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
                else:
                    self.lbl_test_status.setText(f"Connection failed: {msg}")
                    self.lbl_test_status.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            QTimer.singleShot(0, _update)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _save_settings(self):
        # Local Engine Settings
        self.config.model_size = self.combo_local_model.currentText()
        self.config.input_device_index = self.combo_mic.currentData()

        # Hotkeys & Mode
        preset_val = self.combo_hotkey_preset.currentData()
        if preset_val and preset_val != "custom":
            raw_key = preset_val
        else:
            raw_key = display_to_pynput(self.edit_hotkey.text().strip())

        self.config.hotkey = raw_key
        self.config.hotkey_mode = self.combo_hotkey_mode.currentData() or "toggle"
        self.config.auto_paste = self.check_auto_paste.isChecked()
        self.config.copy_to_clipboard = self.check_clipboard.isChecked()

        # System Polish & Context
        self.config.clean_speech = self.check_clean_speech.isChecked()
        self.config.app_context_aware = self.check_app_context.isChecked()
        self.config.play_chimes = self.check_play_chimes.isChecked()

        # Model Security & Privacy Guardrails
        self.config.prompt_injection_guard = self.check_prompt_guard.isChecked()
        self.config.redact_sensitive_pii = self.check_pii_redact.isChecked()
        self.config.strict_offline_mode = self.check_strict_offline.isChecked()

        # AI Cloud Settings
        if self.config.strict_offline_mode:
            self.config.ai_enabled = False
        else:
            self.config.ai_enabled = self.check_ai_enabled.isChecked()

        # Custom Vocabulary
        self.config.custom_vocabulary = [
            w.strip() for w in self.edit_vocabulary.text().split(",") if w.strip()
        ]

        self.config.save()

        # Update running subservices
        if self.ai_service:
            self.ai_service.update_config(self.config)
        if self.hotkey_manager:
            self.hotkey_manager.update_hotkey(self.config.hotkey, self.config.hotkey_mode)

        # Update Top Bar Badges & Sidebar
        readable = hotkey_to_display(self.config.hotkey)
        self.pill_hotkey.setText(readable)
        self.lbl_sidebar_shortcut.setText(readable)
        self.lbl_banner_hint.setText(f"Press <b>{readable}</b> anywhere in Windows to dictate directly to your active cursor.")
        
        mode_label = "Push-to-Talk" if self.config.hotkey_mode == "push_to_talk" else "Toggle"
        self.pill_mode.setText(f"Mode: {mode_label}")
        
        ai_badge = "AI Polish: Active" if (self.config.ai_enabled and not getattr(self.config, "strict_offline_mode", False)) else "AI: Offline"
        self.pill_model.setText(ai_badge)

        QMessageBox.information(self, "Settings Saved", "Preferences updated successfully.")
