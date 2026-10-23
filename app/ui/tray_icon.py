from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


def create_default_tray_pixmap() -> QPixmap:
    """Generates a sleek procedural microphone / circular icon for system tray."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0)) # transparent

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Circle background
    painter.setBrush(QColor(59, 130, 246)) # vibrant blue
    painter.setPen(QColor(255, 255, 255, 200))
    painter.drawEllipse(2, 2, 28, 28)

    # Mic head
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawRoundedRect(12, 7, 8, 12, 4, 4)

    # Stand arc
    painter.setPen(QColor(255, 255, 255))
    painter.drawArc(9, 11, 14, 10, 0, -180 * 16)
    painter.drawLine(16, 21, 16, 25)
    painter.drawLine(12, 25, 20, 25)

    painter.end()
    return pixmap


class SystemTrayManager(QObject):
    """Manages the Windows taskbar system tray icon and menu."""

    show_studio_requested = Signal()
    toggle_dictation_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        icon = QIcon(create_default_tray_pixmap())
        self.tray = QSystemTrayIcon(icon, parent)
        self.tray.setToolTip("Flow STT - Voice Dictation")

        menu = QMenu()
        open_action = menu.addAction("🎙️ Open Studio")
        open_action.triggered.connect(lambda: self.show_studio_requested.emit())

        toggle_action = menu.addAction("● Toggle Dictation")
        toggle_action.triggered.connect(lambda: self.toggle_dictation_requested.emit())

        menu.addSeparator()

        quit_action = menu.addAction("Quit Flow STT")
        quit_action.triggered.connect(lambda: self.quit_requested.emit())

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_studio_requested.emit()

    def show_message(self, title: str, message: str):
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 2500)
