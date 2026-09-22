"""Individual tool-call timeline step widget."""

import html
import json

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget
)

import src.ui.design_tokens as t
from src.ui.icons import get_application_icon, get_default_tool_icon
from src.ui.stylesheet import qss_tool_call_step, qss_tool_code_browser, qss_transparent_surface
from src.ui.widgets.timeline_header import ChevronLabel

CHEVRON_SPACING = 4


class ToolCallStepWidget(QFrame):
    """Une ligne d'étape individuelle dans la timeline Antigravity."""

    toggled = Signal()

    def __init__(self, tool_info: dict, parent=None):
        super().__init__(parent)
        self.tool_info = tool_info
        self.setObjectName("ToolCallStepRow")
        self._build_ui()

    def _build_ui(self):
        status = self.tool_info.get("status", "running")
        name = self.tool_info.get("name", "tool")
        args_raw = self.tool_info.get("arguments", "")
        result_raw = self.tool_info.get("result", "")
        is_expanded = self.tool_info.get("expanded", False)

        self.setStyleSheet(qss_tool_call_step())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ── Ligne d'en-tête de l'étape ────────────────────────────────
        self.header_row = QWidget(self)
        self.header_row.setStyleSheet(qss_transparent_surface())
        self.header_row.setCursor(Qt.PointingHandCursor)

        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(0, 0, 8, 0)
        header_layout.setSpacing(CHEVRON_SPACING)
        self.header_row.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.header_row.setMinimumHeight(24)

        timeline_line = QFrame(self.header_row)
        timeline_line.setFrameShape(QFrame.VLine)
        timeline_line.setFrameShadow(QFrame.Plain)
        timeline_line.setFixedWidth(t.TIMELINE_LINE_WIDTH)
        timeline_line.setStyleSheet(f"color:{t.COLOR_BORDER}; background:{t.COLOR_BORDER};")
        header_layout.addWidget(timeline_line, 0, Qt.AlignVCenter)

        icon_label = QLabel(self.header_row)
        icon_path = self.tool_info.get("icon")
        icon = get_application_icon(icon_path) if icon_path else get_default_tool_icon()
        icon_label.setPixmap(
            icon.pixmap(
                t.ICON_SIZE_TIMELINE,
                t.ICON_SIZE_TIMELINE,
                QIcon.Normal,
                QIcon.On,
            )
        )
        icon_label.setFixedSize(t.ICON_SIZE_TIMELINE, t.ICON_SIZE_TIMELINE)
        icon_label.setStyleSheet(qss_transparent_surface())
        header_layout.addWidget(icon_label, 0, Qt.AlignVCenter)

        # Texte stylisé "Ran <action>"
        verb, target = self._format_step_action(name, status, args_raw)
        self.action_label = QLabel(self.header_row)
        self.action_label.setStyleSheet(qss_transparent_surface())
        self._verb, self._target, self._status = verb, target, status
        self._set_action_label_text(verb, target, status)
        self.action_label.setWordWrap(False)
        self.action_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.action_label.installEventFilter(self)
        header_layout.addWidget(self.action_label, 0, Qt.AlignVCenter)

        # Chevron à droite, pivoté de 90 degrés lorsqu'il est déplié.
        self.chevron = ChevronLabel(self.header_row)
        self.chevron.set_expanded(is_expanded)
        header_layout.addWidget(self.chevron, 0, Qt.AlignRight | Qt.AlignVCenter)
        self._expanded = is_expanded
        if is_expanded:
            self._set_action_label_text(self._verb, self._target, self._status, hover=True)
        self._set_chevron_visible(is_expanded)

        layout.addWidget(self.header_row)

        # ── Panneau de détails dépliable ──────────────────────────────
        self.details_panel = QWidget(self)
        self.details_panel.setStyleSheet(qss_transparent_surface())
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(14, 2, 8, 6)
        details_layout.setSpacing(4)

        # Section Paramètres
        formatted_args = self._format_json_or_text(args_raw)
        if formatted_args:
            lbl_args = QLabel("Arguments", self.details_panel)
            lbl_args.setStyleSheet(self._section_title_style())
            details_layout.addWidget(lbl_args)
            args_browser = self._create_code_browser(formatted_args)
            details_layout.addWidget(args_browser)

        # Section Résultat / Erreur
        formatted_result = self._format_json_or_text(result_raw)
        if formatted_result:
            is_err = status == "error"
            title_text = "Erreur" if is_err else "Résultat"
            lbl_res = QLabel(title_text, self.details_panel)
            lbl_res.setStyleSheet(self._section_title_style(color=t.COLOR_DANGER if is_err else None))
            details_layout.addWidget(lbl_res)
            res_browser = self._create_code_browser(formatted_result, is_err)
            details_layout.addWidget(res_browser)

        self.details_panel.setVisible(is_expanded)
        layout.addWidget(self.details_panel)

        # Clic pour déplier/replier
        self.header_row.mousePressEvent = lambda e: self._toggle_expanded()

    def _format_step_action(self, name: str, status: str, args_raw: str) -> tuple:
        """Détermine le verbe et l'intitulé de l'action selon l'outil exécuté."""
        if status == "running":
            verb = "Exécution de"
        elif status == "error":
            verb = "Failed"
        else:
            verb = "exécuté"

        # Tenter d'extraire les paramètres clés
        param_summary = ""
        if args_raw:
            trimmed = args_raw.strip()
            if trimmed.startswith("{"):
                try:
                    data = json.loads(trimmed)
                    if isinstance(data, dict):
                        # Clés prioritaires pour le résumé
                        for key in ("filename", "name", "path", "filepath", "file", "title", "query", "command"):
                            if key in data and data[key]:
                                val = str(data[key])
                                param_summary = f"— {val}" if key not in ("command", "query") else val
                                break
                except Exception:
                    pass
            elif not trimmed.startswith(("{", "[")):
                param_summary = trimmed

        # Formatage selon l'outil
        if status == "running":
            target = f"« {param_summary or name} »…"
        elif status in {"completed", "done", "success"}:
            skill = str(
                self.tool_info.get("skill_name")
                or self.tool_info.get("skill")
                or "FTNC"
            ).upper()
            tool = str(
                self.tool_info.get("tool_title")
                or self.tool_info.get("tool_name")
                or name
            ).replace("_", " ").strip().capitalize()
            if tool.lower() == "details":
                tool = "Détails"
            target = f"{skill} - {tool}"
        elif name in ("create_docx", "create_pptx", "create_xlsx"):
            target = f"{name} {param_summary}".strip()
        elif name in ("search_web", "web_search"):
            target = f"Search {param_summary}".strip()
        elif name in ("read_file", "view_file"):
            target = f"Read {param_summary}".strip()
        elif name in ("run_command", "powershell", "cmd"):
            target = param_summary if param_summary else name
        else:
            target = f"{name} {param_summary}".strip() if param_summary else name

        # Tronquer si la ligne dépasse 60 caractères pour garder l'alignement
        if len(target) > 60:
            target = target[:57] + "..."

        return verb, target

    def _section_title_style(self, color=None) -> str:
        is_dark = t.is_dark_theme()
        c = color or t.COLOR_TOOL_MUTED
        return f"""
            font-size: {t.SIZE_SM};
            font-weight: 700;
            color: {c};
            background: transparent;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """

    def _create_code_browser(self, text: str, is_error: bool = False) -> QTextBrowser:
        browser = QTextBrowser(self.details_panel)
        browser.setPlainText(text)
        browser.setReadOnly(True)
        browser.setTextInteractionFlags(Qt.TextSelectableByMouse)

        browser.setStyleSheet(qss_tool_code_browser(is_error))
        line_count = min(7, max(2, text.count("\n") + 1))
        browser.setFixedHeight(line_count * 14 + 12)
        return browser

    @staticmethod
    def _format_json_or_text(raw: str) -> str:
        if not raw:
            return ""
        trimmed = raw.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (
            trimmed.startswith("[") and trimmed.endswith("]")
        ):
            try:
                parsed = json.loads(trimmed)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return trimmed

    def _toggle_expanded(self):
        new_state = not self.tool_info.get("expanded", False)
        self._expanded = new_state
        self.tool_info["expanded"] = new_state
        self.details_panel.setVisible(new_state)
        self.chevron.set_expanded(new_state)
        self._set_chevron_visible(new_state)
        self.toggled.emit()

    def _set_chevron_visible(self, visible: bool):
        self.chevron.setVisible(visible)

    def eventFilter(self, watched, event):
        if watched is self.action_label:
            if event.type() == QEvent.Enter:
                self._set_action_label_text(self._verb, self._target, self._status, hover=True)
                self._set_chevron_visible(True)
            elif event.type() == QEvent.Leave:
                self._set_action_label_text(self._verb, self._target, self._status)
                if not self._expanded:
                    self._set_chevron_visible(False)
        return super().eventFilter(watched, event)

    def _set_action_label_text(self, verb: str, target: str, status: str, hover=False):
        if hover:
            verb_color = target_color = t.COLOR_TEXT_PRIMARY
        else:
            is_dark = t.is_dark_theme()
            muted_color = t.COLOR_TEXT_SECONDARY
            target_color = t.COLOR_TOOL_TEXT
            if status == "error":
                verb_color = t.COLOR_DANGER
            elif status == "running":
                verb_color = t.COLOR_TEXT_LINK
            else:
                verb_color = muted_color

        verb_esc = html.escape(verb)
        target_esc = html.escape(target)
        if status in {"completed", "done", "success"}:
            self.action_label.setText(
                f"<span style='color:{target_color}; font-size:{t.SIZE_SM}; font-weight:700;'>"
                f"{target_esc}</span> "
                f"<span style='color:{verb_color}; font-size:{t.SIZE_SM}; font-weight:500;'>"
                f"{verb_esc}</span>"
            )
        else:
            self.action_label.setText(
                f"<span style='color:{verb_color}; font-size:{t.SIZE_SM}; font-weight:500;'>{verb_esc} </span>"
                f"<span style='color:{target_color}; font-family:Consolas, \"Cascadia Code\", monospace; font-size:{t.SIZE_SM};'>{target_esc}</span>"
            )


