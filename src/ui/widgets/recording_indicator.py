"""Fenêtre flottante affichée lors de la captation vocale."""

import time
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.config.schema import APP_DIR, LOGGER
from src.ui.design_tokens import (
    COLOR_PRESS_DARK,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    FONT_DISPLAY,
    FONT_TEXT,
    SIZE_LG,
)
from src.ui.icons import get_logo_pixmap
from src.ui.stylesheet import build_acrylic_window_qss
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.audio_bars import LiveAudioIndicator


class RecordingIndicator(QWidget):
    """Fenêtre vocale avec le même habillage que la fenêtre de réponse."""

    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(240)
        self.started_at = 0.0
        self.phase = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        self.panel.setStyleSheet(
            build_acrylic_window_qss()
            + f"""
            QLabel#VoiceText, QLabel#VoiceClock {{
                background: transparent;
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                font-family: {FONT_TEXT};
                font-size: {SIZE_LG};
            }}
            QLabel#VoiceClock {{ color: {COLOR_TEXT_MUTED}; }}
            """
        )
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame(self.panel)
        self.header = header
        header.setObjectName("Header")
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 1, 9, 0)
        header_layout.setSpacing(7)
        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        icon_label.setPixmap(get_logo_pixmap(16, APP_DIR))
        self.title = QLabel("Assistant", header)
        self.title.setObjectName("TitleLabel")
        self.title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(icon_label)
        header_layout.addWidget(self.title, 1)
        # Espace symétrique afin que le titre reste centré malgré l'icône de gauche.
        title_balance = QWidget(header)
        title_balance.setFixedSize(18, 18)
        header_layout.addWidget(title_balance)
        panel_layout.addWidget(header)

        separator_box = QWidget(self.panel)
        separator_box.setFixedHeight(3)
        separator_layout = QHBoxLayout(separator_box)
        separator_layout.setContentsMargins(14, 0, 14, 0)
        separator = QFrame(separator_box)
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background:{COLOR_PRESS_DARK};border:none;")
        separator_layout.addWidget(separator)
        panel_layout.addWidget(separator_box)

        content = QWidget(self.panel)
        content.setStyleSheet("background:transparent;border:none;")
        row = QVBoxLayout(content)
        row.setContentsMargins(8, 8, 8, 10)
        row.setSpacing(0)
        self.mic = QLabel("🎙", content)
        self.mic.hide()
        self.text = QLabel("", content)
        self.text.setObjectName("VoiceText")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setWordWrap(True)
        self.audio_visual = LiveAudioIndicator(content)
        self.clock = QLabel("00:00", content)
        self.clock.hide()
        row.addWidget(self.audio_visual, 0, Qt.AlignCenter)
        row.addWidget(self.text, 0, Qt.AlignCenter)
        self.text.hide()
        panel_layout.addWidget(content)
        outer.addWidget(self.panel)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)

    def start_recording(self, action_name: str = "") -> None:
        self.started_at = time.monotonic()
        self.phase = False
        self.title.setText(f"Assistant - {action_name}" if action_name else "Assistant")
        self.text.clear()
        self.text.hide()
        self.mic.hide()
        self.clock.hide()
        self.audio_visual.set_level(0)
        self.audio_visual.show()
        self.audio_visual.start()
        self.clock.setText("00:00")
        self.timer.start()
        self.show_at_top()
        self.show()
        self.raise_()
        QTimer.singleShot(0, self.apply_native_effects)

    def show_at_top(self) -> None:
        screen = (
            QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        )
        rect = screen.availableGeometry()
        self.adjustSize()
        self.move(rect.x() + (rect.width() - self.width()) // 2, rect.y() + 18)

    def _tick(self) -> None:
        seconds = int(time.monotonic() - self.started_at)
        self.clock.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")

    def set_level(self, value: float) -> None:
        self.audio_visual.set_level(value)

    def set_status(self, text: str) -> None:
        self.timer.stop()
        self.audio_visual.stop()
        self.audio_visual.hide()
        self.mic.hide()
        self.text.setText(text)
        self.text.setAlignment(Qt.AlignCenter)
        self.text.show()
        self.clock.hide()
        self.show_at_top()
        self.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.apply_native_effects)

    def apply_native_effects(self) -> None:
        try:
            hwnd = int(self.winId())
            apply_acrylic_blur(hwnd, 0xB8F5F5F5)
            apply_rounded_corners(hwnd)
        except (AttributeError, OSError, TypeError, ValueError):
            LOGGER.debug(
                "Effets natifs indisponibles pour l'indicateur vocal",
                exc_info=True,
            )

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel_requested.emit()
        else:
            super().keyPressEvent(event)
