from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
import math
import random


class WaveformWidget(QWidget):
    """Animated sound level visualizer bars."""

    def __init__(self, parent=None, num_bars: int = 5):
        super().__init__(parent)
        self.num_bars = num_bars
        self.current_level = 0.0
        self.setFixedSize(50, 24)

    def set_level(self, level: float):
        self.current_level = max(0.05, min(1.0, level))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = 4
        gap = 4
        total_w = self.num_bars * bar_w + (self.num_bars - 1) * gap
        start_x = (w - total_w) // 2

        # Draw bars
        painter.setPen(Qt.NoPen)
        for i in range(self.num_bars):
            # Create natural wave variation per bar based on volume
            factor = math.sin((i / max(1, self.num_bars - 1)) * math.pi)
            jitter = (random.random() * 0.3) if self.current_level > 0.1 else 0
            bar_h = max(4.0, (self.current_level * 0.7 + factor * 0.3 + jitter) * (h - 4))

            y = (h - bar_h) / 2
            x = start_x + i * (bar_w + gap)

            # Gradient/color: vibrant cyan-purple
            if self.current_level > 0.15:
                color = QColor(99, 102, 241) # Indigo/violet
            else:
                color = QColor(148, 163, 184) # Muted slate

            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)


class FloatingPill(QWidget):
    """Minimalist, stay-on-top floating pill widget for live dictation feedback."""

    # Thread-safe signals
    state_changed = Signal(str, str) # state ("recording", "processing", "ready"), message
    level_updated = Signal(float)

    def __init__(self):
        super().__init__()

        # Window flags: Frameless, always on top, tool window (does not take focus)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._drag_pos = QPoint()

        self._init_ui()
        self._center_bottom()

        # Connect signals
        self.state_changed.connect(self._on_state_changed)
        self.level_updated.connect(self._on_level_updated)

    def _init_ui(self):
        self.setFixedSize(220, 48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        # Status Dot
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        self.dot.setStyleSheet("background-color: #EF4444; border-radius: 5px;")

        # Status Label
        self.status_label = QLabel("Listening...")
        self.status_label.setStyleSheet(
            "color: #F8FAFC; font-family: 'Segoe UI', sans-serif; font-size: 13px; font-weight: 600;"
        )

        # Waveform visualizer
        self.waveform = WaveformWidget(self, num_bars=5)

        layout.addWidget(self.dot)
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.waveform)

    def _center_bottom(self):
        """Positions the pill horizontally centered, near bottom of primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 60
            self.move(x, y)

    def set_recording_state(self, is_recording: bool):
        if is_recording:
            self.state_changed.emit("recording", "Listening...")
        else:
            self.state_changed.emit("processing", "Transcribing...")

    def _on_state_changed(self, state: str, text: str):
        self.status_label.setText(text)
        if state == "recording":
            self.dot.setStyleSheet("background-color: #EF4444; border-radius: 5px;")
            self.show()
        elif state == "processing":
            self.dot.setStyleSheet("background-color: #F59E0B; border-radius: 5px;")
        elif state == "idle":
            self.hide()

    def _on_level_updated(self, level: float):
        self.waveform.set_level(level)

    def paintEvent(self, event):
        """Paints a rounded dark glassmorphic capsule."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background pill
        bg_color = QColor(15, 23, 42, 230) # Slate 900 semi-transparent
        painter.setBrush(QBrush(bg_color))

        # Border
        pen = QPen(QColor(255, 255, 255, 35))
        pen.setWidth(1)
        painter.setPen(pen)

        painter.drawRoundedRect(0, 0, self.width(), self.height(), 24, 24)

    # Allow user to drag the pill around screen
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
