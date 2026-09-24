"""Widget d'affichage d'exécution d'outils style timeline Antigravity IDE.

Reproduit fidèlement l'esthétique Antigravity :
- En-tête de groupe pliable : "Worked for 4m ⌄" / "Working... ⌄"
- Lignes d'étapes sobres : "Ran <action> ›" avec effet pill au survol
- Détails pliables : Code JSON / texte formaté avec syntaxe soignée
- Prise en charge des thèmes sombre et clair.
"""

import re
import time

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t
from src.rendering.markdown import markdown_to_html
from src.ui.status_formatters import (
    format_duration,
    format_thinking_status,
    format_tool_group_status,
)
from src.ui.stylesheet import (
    qss_thinking_details,
    qss_tool_group_header,
    qss_tool_steps_container,
    qss_transparent_surface,
)
from src.ui.widgets.thinking_dots import ShimmerLabel

CHEVRON_SPACING = 4
CHEVRON_FONT_SIZE = 18
CHEVRON_WIDTH = 14
BRAIN_ICON_SVG = (
    '<path d="M9.5 3.5a3 3 0 0 0-5.8 1.1A2.8 2.8 0 0 0 4 10a3 3 0 0 0 1.5 5.6A3 3 0 0 0 11 16V6.5a3 3 0 0 0-1.5-3z"/>'
    '<path d="M14.5 3.5a3 3 0 0 1 5.8 1.1A2.8 2.8 0 0 1 20 10a3 3 0 0 1-1.5 5.6A3 3 0 0 1 13 16V6.5a3 3 0 0 1 1.5-3z"/>'
    '<path d="M9 8H7.5M9 12H7M15 8h1.5M15 12h2M12 6v12"/>'
)


from src.ui.widgets.timeline_header import CollapsibleHeader
from src.ui.widgets.tool_call_step import ToolCallStepWidget


class ToolExecutionGroupWidget(QWidget):
    """Conteneur complet de la timeline d'outils Antigravity pour un tour de conversation.

    Affiche:
    Worked for 4m ⌄
      Ran create_docx — test.docx ›
      Ran Select-String ... ›
    """

    toggled = Signal()

    def __init__(self, tools: list, turn: dict | None = None, parent=None):
        super().__init__(parent)
        self.tools = tools if isinstance(tools, list) else [tools]
        self.turn = turn or {}
        self.setObjectName("ToolExecutionGroup")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(qss_transparent_surface())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        t.is_dark_theme()
        muted_color = t.COLOR_TEXT_SECONDARY

        any_running = any(t.get("status") == "running" for t in self.tools)
        is_group_collapsed = self.turn.get("tools_collapsed", not any_running)

        # ── 1. En-tête groupé façon GitHub Agent ──────────────────────
        duration_text = self._compute_duration_string(any_running)
        step_count = len(self.tools)
        header_title = self._format_header_title(step_count, any_running, duration_text)
        self.header_label = QLabel(header_title, self)
        self.header_label.setStyleSheet(qss_tool_group_header(muted_color))
        self.header_label.installEventFilter(self)
        self.header_label.setFixedHeight(t.HEADER_ROW_HEIGHT)
        self.header_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.header_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.header_btn = CollapsibleHeader(
            self.header_label,
            not is_group_collapsed,
            self,
            icon_svg=BRAIN_ICON_SVG,
        )
        self.header_btn.setObjectName("ToolExecutionHeader")
        self.header_btn.setStyleSheet(qss_transparent_surface())
        self.header_btn.hovered.connect(self._on_header_hovered)
        self.chevron = self.header_btn.chevron
        self._group_expanded = not is_group_collapsed
        self._set_group_chevron_visible(self._group_expanded)

        main_layout.addWidget(self.header_btn, 0, Qt.AlignLeft)

        # ── 2. Conteneur des étapes indenté ───────────────────────────
        self.steps_container = QWidget(self)
        self.steps_container.setStyleSheet(qss_tool_steps_container())
        steps_layout = QVBoxLayout(self.steps_container)
        # Indentation de 12px vers la droite pour les étapes
        steps_layout.setContentsMargins(t.TIMELINE_INDENT, 1, 0, 2)
        steps_layout.setSpacing(1)

        for tool_info in self.tools:
            step_widget = ToolCallStepWidget(tool_info, self.steps_container)
            step_widget.toggled.connect(self._on_step_toggled)
            steps_layout.addWidget(step_widget)

        self.steps_container.setVisible(not is_group_collapsed)
        main_layout.addWidget(self.steps_container, 0, Qt.AlignLeft)
        main_layout.activate()
        self.updateGeometry()
        # Pour un outil unique, le récapitulatif apparaît seulement après
        # l'exécution afin de ne pas dupliquer la ligne de progression.
        if len(self.tools) == 1 and any_running:
            self.header_btn.hide()

        # Clic sur l'en-tête pour replier/déplier toutes les étapes
        self.header_btn.mousePressEvent = lambda e: self._toggle_group()

    def _compute_duration_string(self, any_running: bool) -> str:
        """Calcule la durée formatée (ex: '4m', '12s', '1m 20s')."""
        start = self.turn.get("tool_start_time")
        if not start:
            # S'il n'y a pas de timestamp enregistré, estimer selon le nombre d'outils
            return format_duration(max(1, len(self.tools) * 2))

        end = time.time() if any_running else (self.turn.get("tool_end_time") or time.time())
        return format_duration(end - start)

    @staticmethod
    def _format_header_title(step_count: int, any_running: bool, duration_text: str) -> str:
        return format_tool_group_status(step_count, any_running, duration_text)

    def _toggle_group(self):
        is_collapsed = not self.turn.get("tools_collapsed", False)
        self.turn["tools_collapsed"] = is_collapsed
        self.steps_container.setVisible(not is_collapsed)

        any_running = any(t.get("status") == "running" for t in self.tools)
        duration_text = self._compute_duration_string(any_running)
        step_count = len(self.tools)
        header_title = self._format_header_title(step_count, any_running, duration_text)
        self.header_label.setText(header_title)
        self._group_expanded = not is_collapsed
        self.header_btn.set_expanded(self._group_expanded)
        self.steps_container.adjustSize()
        self.layout().activate()
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            if parent.layout() is not None:
                parent.layout().activate()
            parent.updateGeometry()

        self.toggled.emit()

    def _on_step_toggled(self):
        self.toggled.emit()

    def _on_header_hovered(self, hovered: bool):
        self._header_hovered = hovered

    def _set_group_chevron_visible(self, visible: bool):
        self.header_btn.set_expanded(visible)

class ThinkingGroupWidget(QWidget):
    """Bloc dédié au raisonnement streaming de Gemma, gris et italique."""

    toggled = Signal()

    def __init__(self, parent=None, font_size_offset: int = 0):
        super().__init__(parent)
        self._text = ""
        self._expanded = True
        self._finished = False
        self._duration_seconds = None
        self.font_size_offset = font_size_offset
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title = ShimmerLabel("Raisonnement", self, italic=False)
        self.title.setMinimumWidth(0)
        self.title.setFixedHeight(t.HEADER_ROW_HEIGHT)
        self.title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.title.set_text_color(t.COLOR_TEXT_SECONDARY)
        font_size = max(9, int(t.SIZE_SM.rstrip('px')) + self.font_size_offset)
        title_font = QFont(self.title.font())
        title_font.setPixelSize(font_size)
        self.title.setFont(title_font)
        self.header_row = CollapsibleHeader(
            self.title, True, self, icon_svg=BRAIN_ICON_SVG
        )
        self.header_row.mousePressEvent = lambda _event: self.toggle()
        self.chevron = self.header_row.chevron
        layout.addWidget(self.header_row, 0, Qt.AlignLeft)

        self.details = QLabel(self)
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.RichText)
        self.details.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.details.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.details.setStyleSheet(qss_thinking_details(font_size))
        layout.addWidget(self.details)

    def append_text(self, text: str):
        if not text:
            return
        self._text += text
        self._text = re.sub(r"(?im)^\s*thinking\s+process\s*:\s*", "", self._text)
        self._set_details_markdown()
        self.show()
        self._refresh_details_height()
        self.updateGeometry()

    def set_text(self, text: str):
        self._text = re.sub(
            r"(?im)^\s*thinking\s+process\s*:\s*",
            "",
            text or "",
        )
        self._set_details_markdown()
        self.show()
        self._refresh_details_height()
        self.updateGeometry()

    def _set_details_markdown(self):
        self.details.setText(markdown_to_html(self._text, self.font_size_offset))

    def _refresh_details_height(self, width: int = 0):
        """Mesure le texte avec la largeur réelle du bloc, retours à la ligne inclus."""
        if width <= 0:
            width = self.width() if self.width() > 0 else self.details.width()
            if width <= 0 and self.parentWidget() is not None:
                parent_w = self.parentWidget().width()
                if parent_w > 0:
                    width = parent_w
        if width <= 0:
            return
        height = self.details.heightForWidth(width)
        if height > 0:
            self.details.setFixedHeight(height)
        self.details.updateGeometry()
        self.updateGeometry()
        if self.layout() is not None:
            self.layout().activate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_details_height(event.size().width())

    def clear(self):
        self._text = ""
        self.details.clear()
        self._expanded = True
        self._finished = False
        self._duration_seconds = None
        self.title.set_status_text("Raisonnement")
        self.header_row.set_expanded(True)
        self.header_row.set_animation(True)
        self.hide()

    def collapse(self):
        self._expanded = False
        self._finished = True
        self.details.hide()
        self.title.set_status_text("Raisonnement")
        self.title.set_text_color(t.COLOR_TEXT_SECONDARY)
        self.header_row.set_expanded(False)
        self.header_row.set_animation(False)
        self.layout().activate()
        self.updateGeometry()

    def finish(self, duration_seconds: float):
        """Marque la fin du raisonnement et affiche sa durée."""
        self._expanded = False
        self._finished = True
        self._duration_seconds = max(0, round(duration_seconds))
        self.details.hide()
        self.title.set_status_text(format_thinking_status(duration_seconds))
        self.title.set_text_color(t.COLOR_TEXT_SECONDARY)
        self.header_row.set_expanded(False)
        self.header_row.set_animation(False)
        self.layout().activate()
        self.updateGeometry()

    def toggle(self):
        self._expanded = not self._expanded
        self.details.setVisible(self._expanded)
        if self._finished and self._duration_seconds is not None:
            self.title.set_status_text(
                format_thinking_status(self._duration_seconds)
            )
        else:
            self.title.set_status_text("Raisonnement")
        self.header_row.set_expanded(self._expanded)
        if self._expanded:
            self._refresh_details_height()
        self.layout().activate()
        self.updateGeometry()
        self.toggled.emit()

    def _set_thinking_chevron_visible(self, visible):
        self.chevron.setVisible(visible)


class ToolCallWidget(ToolExecutionGroupWidget):
    """Alias rétrocompatible pour ToolExecutionGroupWidget."""

    def __init__(self, tool_or_tools, parent=None, turn=None):
        if isinstance(tool_or_tools, dict):
            tools = [tool_or_tools]
        else:
            tools = tool_or_tools
        super().__init__(tools=tools, turn=turn or {}, parent=parent)
