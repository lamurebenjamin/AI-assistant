# -*- coding: utf-8 -*-
"""Widget d'affichage d'exécution d'outils style timeline Antigravity IDE.

Reproduit fidèlement l'esthétique Antigravity :
- En-tête de groupe pliable : "Worked for 4m ⌄" / "Working... ⌄"
- Lignes d'étapes sobres : "Ran <action> ›" avec effet pill au survol
- Détails pliables : Code JSON / texte formaté avec syntaxe soignée
- Prise en charge des thèmes sombre et clair.
"""

import html
import json
import time
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t


class ToolCallStepWidget(QFrame):
    """Une ligne d'étape individuelle dans la timeline Antigravity."""

    toggled = pyqtSignal()

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

        is_dark = t.is_dark_theme()
        hover_bg = "rgba(255, 255, 255, 12)" if is_dark else "rgba(0, 0, 0, 10)"

        self.setStyleSheet(f"""
            QFrame#ToolCallStepRow {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 0px;
                margin: 0px;
            }}
            QFrame#ToolCallStepRow:hover {{
                background: {hover_bg};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ── Ligne d'en-tête de l'étape ────────────────────────────────
        self.header_row = QWidget(self)
        self.header_row.setStyleSheet("background: transparent;")
        self.header_row.setCursor(Qt.PointingHandCursor)

        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(6, 4, 8, 4)
        header_layout.setSpacing(6)

        # Texte stylisé "Ran <action>"
        verb, target = self._format_step_action(name, status, args_raw)
        self.action_label = QLabel(self.header_row)
        self.action_label.setStyleSheet("background: transparent;")
        self._set_action_label_text(verb, target, status)
        self.action_label.setWordWrap(False)
        header_layout.addWidget(self.action_label, 1, Qt.AlignVCenter)

        # Chevron à droite (› ou ⌄)
        chevron_color = t.COLOR_TEXT_MUTED if hasattr(t, "COLOR_TEXT_MUTED") else "#6E7681"
        self.chevron = QLabel("⌄" if is_expanded else "›", self.header_row)
        self.chevron.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 700;
            color: {chevron_color};
            background: transparent;
        """)
        self.chevron.setFixedWidth(14)
        self.chevron.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(self.chevron, 0, Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.header_row)

        # ── Panneau de détails dépliable ──────────────────────────────
        self.details_panel = QWidget(self)
        self.details_panel.setStyleSheet("background: transparent;")
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

    def _set_action_label_text(self, verb: str, target: str, status: str):
        is_dark = t.is_dark_theme()
        muted_color = "#8B949E" if is_dark else "#656D76"
        target_color = "#C9D1D9" if is_dark else "#24292F"
        if status == "error":
            verb_color = t.COLOR_DANGER
        elif status == "running":
            verb_color = "#58A6FF" if is_dark else t.COLOR_PRIMARY
        else:
            verb_color = muted_color

        verb_esc = html.escape(verb)
        target_esc = html.escape(target)

        self.action_label.setText(
            f"<span style='color:{verb_color}; font-size:11px; font-weight:500;'>{verb_esc} </span>"
            f"<span style='color:{target_color}; font-family:Consolas, \"Cascadia Code\", monospace; font-size:11px;'>{target_esc}</span>"
        )

    @staticmethod
    def _format_step_action(name: str, status: str, args_raw: str) -> tuple:
        """Détermine le verbe et l'intitulé de l'action selon l'outil exécuté."""
        if status == "running":
            verb = "Running"
        elif status == "error":
            verb = "Failed"
        else:
            verb = "Ran"

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
        if name in ("create_docx", "create_pptx", "create_xlsx"):
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
        c = color or ("#8B949E" if is_dark else "#656D76")
        return f"""
            font-size: 9px;
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

        is_dark = t.is_dark_theme()
        code_bg = "rgba(0, 0, 0, 45)" if is_dark else "rgba(0, 0, 0, 6)"
        code_border = "rgba(255, 255, 255, 14)" if is_dark else "rgba(0, 0, 0, 15)"
        text_color = t.COLOR_DANGER if is_error else ("#C9D1D9" if is_dark else "#24292F")

        browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {code_bg};
                color: {text_color};
                border: 1px solid {code_border};
                border-radius: 4px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 10px;
                padding: 4px 6px;
            }}
        """)
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
        self.tool_info["expanded"] = new_state
        self.details_panel.setVisible(new_state)
        self.chevron.setText("⌄" if new_state else "›")
        self.toggled.emit()


class ToolExecutionGroupWidget(QWidget):
    """Conteneur complet de la timeline d'outils Antigravity pour un tour de conversation.

    Affiche:
    Worked for 4m ⌄
      Ran create_docx — test.docx ›
      Ran Select-String ... ›
    """

    toggled = pyqtSignal()

    def __init__(self, tools: list, turn: dict = None, parent=None):
        super().__init__(parent)
        self.tools = tools if isinstance(tools, list) else [tools]
        self.turn = turn or {}
        self.setObjectName("ToolExecutionGroup")
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("background: transparent; border: none;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        is_dark = t.is_dark_theme()
        muted_color = "#8B949E" if is_dark else "#656D76"

        is_group_collapsed = self.turn.get("tools_collapsed", False)
        any_running = any(t.get("status") == "running" for t in self.tools)

        # ── 1. En-tête "Worked for 4m ⌄" ──────────────────────────────
        self.header_btn = QWidget(self)
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(4, 2, 8, 2)
        header_layout.setSpacing(4)

        duration_text = self._compute_duration_string(any_running)
        header_title = f"Working... ({duration_text})" if any_running else f"Worked for {duration_text}"
        chevron_symbol = "›" if is_group_collapsed else "⌄"

        self.header_label = QLabel(f"{header_title} {chevron_symbol}", self.header_btn)
        self.header_label.setStyleSheet(f"""
            font-family: {t.FONT_TEXT};
            font-size: 11px;
            font-weight: 500;
            color: {muted_color};
            background: transparent;
        """)
        header_layout.addWidget(self.header_label, 0, Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addStretch(1)

        main_layout.addWidget(self.header_btn)

        # ── 2. Conteneur des étapes indenté ───────────────────────────
        self.steps_container = QWidget(self)
        self.steps_container.setStyleSheet("background: transparent;")
        steps_layout = QVBoxLayout(self.steps_container)
        # Indentation de 12px vers la droite pour les étapes
        steps_layout.setContentsMargins(12, 1, 0, 2)
        steps_layout.setSpacing(2)

        for tool_info in self.tools:
            step_widget = ToolCallStepWidget(tool_info, self.steps_container)
            step_widget.toggled.connect(self._on_step_toggled)
            steps_layout.addWidget(step_widget)

        self.steps_container.setVisible(not is_group_collapsed)
        main_layout.addWidget(self.steps_container)

        # Clic sur l'en-tête pour replier/déplier toutes les étapes
        self.header_btn.mousePressEvent = lambda e: self._toggle_group()

    def _compute_duration_string(self, any_running: bool) -> str:
        """Calcule la durée formatée (ex: '4m', '12s', '1m 20s')."""
        start = self.turn.get("tool_start_time")
        if not start:
            # S'il n'y a pas de timestamp enregistré, estimer selon le nombre d'outils
            return f"{max(1, len(self.tools) * 2)}s"

        end = time.time() if any_running else (self.turn.get("tool_end_time") or time.time())
        diff = max(0.5, end - start)

        if diff < 1:
            return "< 1s"
        elif diff < 60:
            return f"{int(diff)}s"
        else:
            mins = int(diff // 60)
            secs = int(diff % 60)
            return f"{mins}m {secs}s" if secs > 0 else f"{mins}m"

    def _toggle_group(self):
        is_collapsed = not self.turn.get("tools_collapsed", False)
        self.turn["tools_collapsed"] = is_collapsed
        self.steps_container.setVisible(not is_collapsed)

        any_running = any(t.get("status") == "running" for t in self.tools)
        duration_text = self._compute_duration_string(any_running)
        header_title = f"Working... ({duration_text})" if any_running else f"Worked for {duration_text}"
        chevron_symbol = "›" if is_collapsed else "⌄"
        self.header_label.setText(f"{header_title} {chevron_symbol}")

        self.toggled.emit()

    def _on_step_toggled(self):
        self.toggled.emit()


class ToolCallWidget(ToolExecutionGroupWidget):
    """Alias rétrocompatible pour ToolExecutionGroupWidget."""

    def __init__(self, tool_or_tools, parent=None, turn=None):
        if isinstance(tool_or_tools, dict):
            tools = [tool_or_tools]
        else:
            tools = tool_or_tools
        super().__init__(tools=tools, turn=turn or {}, parent=parent)
