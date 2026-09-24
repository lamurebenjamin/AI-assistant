"""Fenêtre flottante affichée lors de la captation vocale."""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t
from src.config.schema import LOGGER
from src.ui.stylesheet import qss_voice_recording_indicator
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.audio_bars import LiveAudioIndicator
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.window_chrome import WindowChrome


class RecordingIndicator(QWidget):
    """Fenêtre vocale avec le même habillage que la fenêtre de réponse."""

    cancel_requested = Signal()

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
        self.setFixedWidth(t.RECORDING_INDICATOR_WIDTH)
        self.started_at = 0.0
        self.phase = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        self.panel.setStyleSheet(self._voice_qss())
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = WindowChrome("Assistant", self.panel, centered=True)
        self.header = header
        self.title = header.title_label
        panel_layout.addWidget(header)

        self.separator_wrapper = HairlineSeparator(
            self.panel, inset=t.SEPARATOR_INSET_COMPACT
        )
        panel_layout.addWidget(self.separator_wrapper)

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

    def _voice_qss(self) -> str:
        return qss_voice_recording_indicator()

    def refresh_theme(self) -> None:
        if hasattr(self, "panel"):
            self.panel.setStyleSheet(self._voice_qss())
        if hasattr(self, "separator_wrapper"):
            self.separator_wrapper.refresh_theme()
        if hasattr(self, "header"):
            self.header.refresh_logo()

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
            apply_acrylic_blur(hwnd)
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
