"""Construction et presentation de la fenetre flottante."""

import re

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from qfluentwidgets import SmoothScrollArea

import src.ui.design_tokens as t
from src.ui.design_tokens import ICON_SIZE_BUTTON, ICON_SIZE_CLOSE, ICON_SIZE_COPY
from src.ui.fluent_compat import install_tooltip
from src.ui.icons import ICONS_DARK
from src.ui.stylesheet import (
    build_acrylic_window_qss,
    qss_assistant_body,
    qss_scrollbar_hidden_horizontal,
)
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.tool_call_widget import ThinkingGroupWidget
from src.ui.widgets.window_chrome import WindowChrome


def initUI(self):
    self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    self.setAttribute(Qt.WA_TranslucentBackground, True)
    self.setObjectName("AssistantWindow")

    self.resize(390, 35)
    self.setMinimumSize(250, 35)
    self.setMaximumSize(1400, 900)

    self.layout = QVBoxLayout(self)
    self.layout.setContentsMargins(0, 0, 0, 0)
    self.layout.setSpacing(0)

    self.panel = QFrame(self)
    self.panel.setObjectName("AcrylicPanel")
    self.panel.setStyleSheet(
        build_acrylic_window_qss(font_offset=1)
        + qss_assistant_body()
        + qss_scrollbar_hidden_horizontal()
    )

    panel_layout = QVBoxLayout(self.panel)
    panel_layout.setContentsMargins(0, 0, 0, 0)
    panel_layout.setSpacing(0)

    header = WindowChrome("Transcript", self.panel)
    header.mousePressEvent = self.mousePressEvent
    header.mouseMoveEvent = self.mouseMoveEvent
    header.mouseReleaseEvent = self.mouseReleaseEvent
    self.chrome = header
    self.header_icon_label = header.icon_label
    self.title_label = header.title_label

    self.speak_button = AnimatedHeaderButton(ICONS_DARK["speak"], "Lire la réponse à haute voix", header, is_audio=True)
    self.speak_button.setIconSize(QSize(ICON_SIZE_BUTTON, ICON_SIZE_BUTTON))
    self.speak_button.clicked.connect(self.toggle_speech)
    header.add_action(self.speak_button)

    self.copy_button = AnimatedHeaderButton(ICONS_DARK["copy"], "Copier la réponse", header)
    self.copy_button.setIconSize(QSize(ICON_SIZE_COPY, ICON_SIZE_COPY))
    self.copy_button.clicked.connect(self.copy_response)
    header.add_action(self.copy_button)

    self.close_button = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", header)
    self.close_button.setIconSize(QSize(ICON_SIZE_CLOSE, ICON_SIZE_CLOSE))
    self.close_button.clicked.connect(self.close_response_window)
    header.add_action(self.close_button)
    panel_layout.addWidget(header)
    self.separator_container = HairlineSeparator(self.panel)
    self.separator_wrapper = self.separator_container
    self.separator = self.separator_container.line
    panel_layout.addWidget(self.separator_container)

    self.thinking_widget = ThinkingGroupWidget(self.panel)
    self.thinking_widget.hide()
    panel_layout.addWidget(self.thinking_widget)

    self.scroll_area = SmoothScrollArea(self.panel)
    self.scroll_area.setWidgetResizable(True)
    self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.scroll_area.setFrameShape(QFrame.NoFrame)
    self.scroll_area.viewport().setAutoFillBackground(False)

    self.label = QLabel("Attente...")
    self.label.setWordWrap(True)
    self.label.setTextFormat(Qt.RichText)
    self.label.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
    )
    self.label.setOpenExternalLinks(False)
    self.label.linkActivated.connect(self.open_response_link)
    self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    self.label.setContentsMargins(0, 0, 0, 0)
    self.label.setMinimumWidth(0)
    self.label.setObjectName("TranscriptBody")
    self.label.setStyleSheet("")

    pal = self.label.palette()
    pal.setColor(QPalette.Highlight, QColor(t.COLOR_PRIMARY_LIGHT))
    pal.setColor(QPalette.HighlightedText, QColor(t.COLOR_TEXT_PRIMARY))
    self.label.setPalette(pal)
    self.scroll_area.setWidget(self.label)
    panel_layout.addWidget(self.scroll_area, 1)

    # Visible uniquement pendant l'exécution d'un outil.
    self.tool_status_label = QLabel("", self.panel)
    self.tool_status_label.setObjectName("ToolStatus")
    self.tool_status_label.setTextFormat(Qt.PlainText)
    self.tool_status_label.setStyleSheet("")
    self.tool_status_label.hide()
    panel_layout.addWidget(self.tool_status_label)

    self.layout.addWidget(self.panel)


def refresh_theme(self) -> None:
    if not hasattr(self, "panel"):
        return
    self.panel.setStyleSheet(
        build_acrylic_window_qss(font_offset=1)
        + qss_assistant_body()
        + qss_scrollbar_hidden_horizontal()
    )
    pal = self.label.palette()
    pal.setColor(QPalette.Highlight, QColor(t.COLOR_PRIMARY_LIGHT))
    pal.setColor(QPalette.HighlightedText, QColor(t.COLOR_TEXT_PRIMARY))
    self.label.setPalette(pal)
    if hasattr(self, "separator_wrapper"):
        self.separator_wrapper.refresh_theme()
    if hasattr(self, "chrome"):
        self.chrome.refresh_logo()
    self.close_button.setIcon(ICONS_DARK["close"])
    speaking = self.tts_thread is not None and self.tts_thread.isRunning()
    self.speak_button.setIcon(ICONS_DARK["stop"] if speaking else ICONS_DARK["speak"])
    self.copy_button.setIcon(ICONS_DARK["copy"])
    if hasattr(self, "recording_indicator"):
        self.recording_indicator.refresh_theme()


def update_window_title(self):
    title = re.sub(r"\s+", " ", self.selected_text).strip() if self.selected_text else ""
    self.title_label.setText(title or "…")
    install_tooltip(self.title_label, title)


def animate_copy_button(self):
    """Remplace brièvement l'icône Copier par une coche, puis la restaure."""
    self.copy_animation_id = getattr(self, "copy_animation_id", 0) + 1
    animation_id = self.copy_animation_id

    if hasattr(self, "copy_animation"):
        self.copy_animation.stop()

    def animate_icon_size(start_size, end_size, duration, on_finished=None):
        if animation_id != self.copy_animation_id:
            return
        self.copy_animation = QPropertyAnimation(self.copy_button, b"iconSize", self)
        self.copy_animation.setDuration(duration)
        self.copy_animation.setStartValue(start_size)
        self.copy_animation.setEndValue(end_size)
        self.copy_animation.setEasingCurve(QEasingCurve.InOutCubic)
        if on_finished is not None:
            self.copy_animation.finished.connect(on_finished)
        self.copy_animation.start()

    def show_check():
        if animation_id != self.copy_animation_id:
            return
        self.copy_button.setIcon(ICONS_DARK["check"])
        animate_icon_size(QSize(8, 8), QSize(17, 17), 160, schedule_restore)

    def schedule_restore():
        QTimer.singleShot(1100, restore_copy)

    def restore_copy():
        if animation_id != self.copy_animation_id:
            return

        def show_copy():
            if animation_id != self.copy_animation_id:
                return
            self.copy_button.setIcon(ICONS_DARK["copy"])
            animate_icon_size(QSize(8, 8), QSize(17, 17), 160)

        animate_icon_size(QSize(17, 17), QSize(8, 8), 120, show_copy)

    animate_icon_size(QSize(17, 17), QSize(8, 8), 120, show_check)


def apply_native_window_effects(self):
    hwnd = int(self.winId())
    apply_acrylic_blur(hwnd)
    apply_rounded_corners(hwnd)
    self.update_rounded_mask()
    QTimer.singleShot(0, self.update_rounded_mask)
