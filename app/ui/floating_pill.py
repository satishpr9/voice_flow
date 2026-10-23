import math
import random
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QLinearGradient, QFont,
    QPainterPath, QCursor
)
from PySide6.QtWidgets import QWidget, QApplication, QGraphicsDropShadowEffect


class FluidWaveform(QWidget):
    """Organic, spring-damped fluid waveform bars reacting to microphone voice levels."""

    def __init__(self, parent=None, num_bars: int = 7):
        super().__init__(parent)
        self.num_bars = num_bars
        self.target_level = 0.05
        self.bar_heights = [4.0] * num_bars
        self.setFixedSize(54, 28)

        # 60 FPS animation timer for organic physics / fluid decay
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_physics)
        self.anim_timer.start(16) # ~60 fps

    def set_level(self, level: float):
        self.target_level = max(0.04, min(1.0, level))

    def _update_physics(self):
        # Damped spring smoothing per bar
        for i in range(self.num_bars):
            # Centered bell-curve multiplier so middle bars are more expressive
            center_factor = math.sin((i / max(1, self.num_bars - 1)) * math.pi)
            jitter = (random.random() - 0.5) * 0.15 if self.target_level > 0.1 else 0.0
            factor = max(0.2, center_factor * 0.8 + 0.2 + jitter)

            target_h = max(4.0, (self.target_level * factor) * (self.height() - 6))
            # Smooth interpolation towards target
            self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.35

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = 3.5
        gap = 4.0
        total_w = self.num_bars * bar_w + (self.num_bars - 1) * gap
        start_x = (w - total_w) / 2.0

        for i in range(self.num_bars):
            bar_h = min(float(h - 4), self.bar_heights[i])
            x = start_x + i * (bar_w + gap)
            y = (h - bar_h) / 2.0

            # Gradient from violet-blue to cyan-purple (Wispr Flow gradient)
            grad = QLinearGradient(x, y, x, y + bar_h)
            if self.target_level > 0.12:
                grad.setColorAt(0.0, QColor(139, 92, 246))  # Vibrant Purple (#8B5CF6)
                grad.setColorAt(1.0, QColor(59, 130, 246))  # Electric Blue (#3B82F6)
            else:
                grad.setColorAt(0.0, QColor(100, 116, 139)) # Muted Slate
                grad.setColorAt(1.0, QColor(71, 85, 105))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.75, 1.75)


class FloatingPill(QWidget):
    """Wispr Flow style minimalist floating capsule widget.
    
    Features:
    - Frosted dark glassmorphism with glowing border
    - Fluid real-time audio waveform
    - Live recording elapsed timer
    - Cancel button (✕)
    - Zero focus stealing (preserves cursor in Word/VS Code/browser)
    - Draggable position memory
    """

    state_changed = Signal(str, str) # state ("recording", "processing", "success", "idle")
    level_updated = Signal(float)
    live_text_updated = Signal(str)
    cancel_requested = Signal()

    def __init__(self):
        super().__init__()

        # Window configuration: Frameless, stay on top, no focus stealing
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.current_state = "idle" # "recording", "processing", "success", "idle"
        self.status_text = "Listening..."
        self.live_text = ""
        self.elapsed_seconds = 0
        self._pulse_phase = 0.0
        self._drag_pos = QPoint()

        # Capsule size with room for live streaming transcript
        self.setFixedSize(380, 48)

        # Drop shadow for floating glass effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        # Pulse timer for recording dot / glowing edge
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._on_pulse)
        self.pulse_timer.start(30)

        # Clock timer for elapsed recording time
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._on_tick)

        # Auto-hide timer for success state
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self._finish_hide)

        # Waveform visualizer child widget positioned on the right
        self.waveform = FluidWaveform(self, num_bars=6)
        self.waveform.move(292, 10)

        # Internal signal wiring
        self.state_changed.connect(self._apply_state)
        self.level_updated.connect(self.waveform.set_level)
        self.live_text_updated.connect(self._on_live_text)

        self._center_bottom()

    def _center_bottom(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 72
            self.move(x, y)

    def _on_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * math.pi)
        if self.isVisible() and self.current_state in ("recording", "processing"):
            self.update()

    def _on_tick(self):
        self.elapsed_seconds += 1
        self.update()

    def set_recording(self):
        self.elapsed_seconds = 0
        self.live_text = ""
        self.clock_timer.start(1000)
        self.state_changed.emit("recording", "Listening...")

    def _on_live_text(self, text: str):
        if self.current_state == "recording":
            self.live_text = text.strip()
            self.update()

    def set_processing(self):
        self.clock_timer.stop()
        self.state_changed.emit("processing", "Flowing...")

    def set_success(self, message: str = "Pasted!"):
        self.clock_timer.stop()
        self.state_changed.emit("success", message)
        self.auto_hide_timer.start(750) # Auto-hide after 750ms

    def set_idle(self):
        self.clock_timer.stop()
        self.state_changed.emit("idle", "")

    def _finish_hide(self):
        self.current_state = "idle"
        self.hide()

    def _apply_state(self, state: str, text: str):
        self.current_state = state
        self.status_text = text

        if state == "recording":
            self.waveform.show()
            self.show()
        elif state == "processing":
            self.waveform.hide()
            self.show()
        elif state == "success":
            self.waveform.hide()
            self.show()
        elif state == "idle":
            self.hide()

        self.update()

    def paintEvent(self, event):
        if self.current_state == "idle":
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        # 1. Dark Acrylic Frosted Glass Background (#0F1117 with 95% opacity)
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        bg_color = QColor(15, 17, 23, 242)
        painter.fillPath(bg_path, QBrush(bg_color))

        # 2. Glowing Border (Wispr Flow subtle iridescent border)
        glow_val = (math.sin(self._pulse_phase) + 1.0) / 2.0 # 0.0 to 1.0
        if self.current_state == "recording":
            border_color = QColor(139, 92, 246, int(70 + glow_val * 90)) # Pulsing violet
        elif self.current_state == "processing":
            border_color = QColor(59, 130, 246, int(90 + glow_val * 110)) # Pulsing electric blue
        else:
            border_color = QColor(34, 197, 94, 200) # Crisp green

        border_pen = QPen(border_color, 1.2)
        painter.strokePath(bg_path, border_pen)

        # 3. Status Indicator Dot or Icon
        if self.current_state == "recording":
            # Pulsing Red/Coral recording dot
            pulse_radius = 4.0 + glow_val * 1.5
            dot_color = QColor(239, 68, 68)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QRectF(16 - pulse_radius, h / 2.0 - pulse_radius, pulse_radius * 2, pulse_radius * 2))

            # Live Timer Text (e.g., 0:04)
            mins = self.elapsed_seconds // 60
            secs = self.elapsed_seconds % 60
            time_str = f"{mins}:{secs:02d}"

            painter.setPen(QColor(241, 245, 249))
            font_timer = QFont("Segoe UI", 9, QFont.Bold)
            painter.setFont(font_timer)
            painter.drawText(QRectF(26, 0, 42, h), Qt.AlignVCenter | Qt.AlignLeft, time_str)

            # Center: Real-time Live Streaming Transcript
            if self.live_text:
                painter.setPen(QColor(248, 250, 252))
                font_live = QFont("Segoe UI", 9, QFont.DemiBold)
                painter.setFont(font_live)
                elided = painter.fontMetrics().elidedText(f'"{self.live_text}"', Qt.ElideLeft, 210)
                painter.drawText(QRectF(70, 0, 214, h), Qt.AlignVCenter | Qt.AlignLeft, elided)
            else:
                painter.setPen(QColor(148, 163, 184))
                font_hint = QFont("Segoe UI", 9, QFont.Normal)
                painter.setFont(font_hint)
                painter.drawText(QRectF(70, 0, 214, h), Qt.AlignVCenter | Qt.AlignLeft, "Listening...")

            # Cancel Button '✕' on the far right
            painter.setPen(QColor(148, 163, 184))
            font_x = QFont("Segoe UI", 10, QFont.Normal)
            painter.setFont(font_x)
            painter.drawText(QRectF(w - 24, 0, 18, h), Qt.AlignVCenter | Qt.AlignLeft, "✕")

        elif self.current_state == "processing":
            # Shimmering "Flowing..." spinner / dots
            painter.setPen(QColor(192, 132, 252)) # Light purple
            font = QFont("Segoe UI", 10, QFont.DemiBold)
            painter.setFont(font)
            
            dots = "." * (int(self._pulse_phase * 1.5) % 4)
            display_text = f"Flowing{dots}"
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, display_text)

        elif self.current_state == "success":
            # Checkmark + "Pasted!"
            painter.setPen(QColor(74, 222, 128)) # Emerald Green
            font = QFont("Segoe UI", 10, QFont.DemiBold)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, f"✓ {self.status_text}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if user clicked the '✕' cancel button on the right edge
            if event.position().x() >= self.width() - 32 and self.current_state == "recording":
                self.cancel_requested.emit()
                event.accept()
                return

            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
