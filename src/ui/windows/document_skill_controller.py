"""Menu de skills, tags et commandes slash du dialogue documentaire."""
import html
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Action as FluentAction
from qfluentwidgets import RoundMenu

import src.ui.design_tokens as t
from core.skill_manager import SkillManager
from src.ui.icons import get_application_icon, get_default_tool_icon


def _create_add_menu(self) -> RoundMenu:
    menu = RoundMenu(parent=self)
    menu.setObjectName("ComposerAddMenu")

    # 1. Option Ajouter un PDF ou une image
    act_add_file = FluentAction("Ajouter un PDF ou une image")
    act_add_file.triggered.connect(self._choose_files)
    menu.addAction(act_add_file)

    # 2. Séparateur
    menu.addSeparator()

    # 3. Liste des skills découverts avec sous-menus
    skill_mgr = getattr(self, "skill_manager", None)
    if skill_mgr is None and self.host is not None:
        skill_mgr = getattr(self.host, "skill_manager", None)
    if skill_mgr is None:
        skill_mgr = SkillManager()
        skill_mgr.discover()
        self.skill_manager = skill_mgr

    discovered_skills = sorted(skill_mgr.skills.keys()) if skill_mgr.skills else skill_mgr.list_skills()
    if not discovered_skills:
        discovered_skills = skill_mgr.discover()

    skill_titles = {
        "pdf": "Document PDF (.pdf)",
        "docx": "Document Word (.docx)",
        "excel": "Classeur Excel (.xlsx)",
        "pptx": "Présentation PowerPoint (.pptx)",
    }
    tool_titles = {
        "create_pdf": "Créer un document PDF",
        "create_docx": "Créer un document Word",
        "create_excel": "Créer un classeur Excel",
        "create_pptx": "Créer une présentation PowerPoint",
        "Liste": "Liste des FTNC",
        "Details": "Détails d'une FTNC",
        "Détails": "Détails d'une FTNC",
    }

    for skill_name in discovered_skills:
        skill_display = skill_titles.get(skill_name, f"Skill {skill_name.capitalize()}")
        sub_menu = RoundMenu(skill_display, parent=menu)
        sub_menu.setObjectName("ComposerAddMenu")

        skill_tools = [
            t for t in skill_mgr.tools.values()
            if t.get("skill") == skill_name
        ]
        if not skill_tools:
            act_none = FluentAction("Aucune action disponible")
            act_none.setEnabled(False)
            sub_menu.addAction(act_none)
        else:
            for tool in skill_tools:
                t_name = tool.get("name", "")
                t_desc = tool.get("description", "")
                t_title = tool_titles.get(t_name, t_name.replace("_", " ").capitalize())
                act_tool = FluentAction(t_title)
                if t_desc:
                    act_tool.setToolTip(t_desc)
                act_tool.triggered.connect(
                    lambda checked=False, s=skill_name, t=t_name: self._on_skill_tool_selected(s, t)
                )
                sub_menu.addAction(act_tool)

        menu.addMenu(sub_menu)

    return menu


def _show_add_menu(self):
    menu = self._create_add_menu()
    btn_pos = self.add_button.mapToGlobal(QPoint(0, 0))
    menu_size = menu.sizeHint()
    target_y = btn_pos.y() - menu_size.height() - 4
    screen = QApplication.screenAt(btn_pos) or QApplication.primaryScreen()
    if screen:
        avail = screen.availableGeometry()
        if target_y < avail.top():
            target_y = btn_pos.y() + self.add_button.height() + 4
    menu.exec(QPoint(btn_pos.x(), target_y))


def _on_skill_tool_selected(self, skill_name: str, tool_name: str):
    self._select_skill_tool(skill_name, tool_name)


def _skill_tool_details(self, skill_name, tool_name):
    skill_manager = self.skill_manager
    info = skill_manager.get_tool(tool_name)
    skill = skill_manager.get_skill(skill_name)
    skill_title = str(getattr(skill, "name", skill_name)).strip() or skill_name
    tool_title = tool_name.replace("_", " ").capitalize()
    if tool_name in {"create_pdf", "create_docx", "create_excel", "create_pptx"}:
        tool_title = {
            "create_pdf": "Créer un document PDF",
            "create_docx": "Créer un document Word",
            "create_excel": "Créer un classeur Excel",
            "create_pptx": "Créer une présentation PowerPoint",
        }[tool_name]
    parameters = info.get("parameters") or {}
    required = parameters.get("required") or []
    icon_path = skill_manager.get_skill_icon(skill_name)
    return {
        "skill_name": skill_name,
        "tool_name": tool_name,
        "title": f"{skill_title} - {tool_title}",
        "icon": icon_path,
        "requires_arguments": bool(required),
    }


def _set_skill_tag(self, tag):
    self._pending_skill_tag = tag
    icon_path = tag.get("icon")
    icon_html = ""
    if icon_path:
        icon_html = (
            f'<img src="{Path(icon_path).as_uri()}" width="18" height="18" '
            'style="vertical-align:middle;">&nbsp;'
        )
    tag_html = (
        f'<span style="background-color:{t.COLOR_PRIMARY_LIGHT}; '
        f'color:{t.COLOR_TEXT_PRIMARY}; font-weight:600; '
        f'padding:0 5px 1px; vertical-align:middle;">{icon_html}'
        f'{html.escape(tag["title"])}</span>&nbsp;'
    )
    self._setting_skill_text = True
    cursor = self.question.textCursor()
    cursor.movePosition(QTextCursor.Start)
    previous_text = self.question.toPlainText()
    cursor.insertHtml(tag_html)
    self.question.setTextCursor(cursor)
    inserted_length = max(1, len(self.question.toPlainText()) - len(previous_text))
    self.question.set_skill_tag_range(0, inserted_length)
    self._setting_skill_text = False
    self.skill_tag.hide()


def _clear_skill_tag_when_erased(self):
    if (
        not self._setting_skill_text
        and self._pending_skill_tag
        and not self.question.toPlainText().replace("\uFFFC", "").strip()
    ):
        self._pending_forced_tool = None
        self._clear_skill_tag()


def _clear_skill_tag(self):
    title = str((self._pending_skill_tag or {}).get("title", ""))
    if title:
        self._setting_skill_text = True
        self.question.remove_skill_tag()
        self._setting_skill_text = False
    self._pending_skill_tag = None
    self.skill_tag.hide()


def _select_skill_tool(self, skill_name, tool_name, existing_text=""):
    tag = self._skill_tool_details(skill_name, tool_name)
    self._setting_skill_text = True
    self.question.setPlainText(existing_text)
    self._setting_skill_text = False
    self._set_skill_tag(tag)
    self._pending_forced_tool = tool_name
    self.question.setFocus()
    if tag["requires_arguments"]:
        self._update_send_visibility()
        self._update_question_height()


def _build_slash_actions(self):
    """Construit la liste d'actions à partir des skills découverts."""
    skill_mgr = getattr(self, "skill_manager", None)
    if skill_mgr is None and self.host is not None:
        skill_mgr = getattr(self.host, "skill_manager", None)
    if skill_mgr is None:
        skill_mgr = SkillManager()
        skill_mgr.discover()
        self.skill_manager = skill_mgr

    skill_titles = {
        "pdf": "Document PDF",
        "docx": "Document Word",
        "excel": "Classeur Excel",
        "pptx": "Présentation PowerPoint",
        "ftnc": "FTNC",
    }
    tool_titles = {
        "create_pdf": "Créer un document PDF",
        "create_docx": "Créer un document Word",
        "create_excel": "Créer un classeur Excel",
        "create_pptx": "Créer une présentation PowerPoint",
    }
    actions = []
    discovered = sorted(skill_mgr.skills.keys()) if skill_mgr.skills else skill_mgr.list_skills()
    if not discovered:
        discovered = skill_mgr.discover()

    for skill_name in discovered:
        skill_tools = [
            t for t in skill_mgr.tools.values()
            if t.get("skill") == skill_name
        ]
        for tool in skill_tools:
            t_name = tool.get("name", "")
            t_desc = tool.get("description", "")
            t_title = tool_titles.get(t_name, t_name.replace("_", " ").capitalize())
            skill_icon = skill_mgr.get_skill_icon(skill_name)
            icon = (
                get_application_icon(skill_icon)
                if skill_icon
                else get_default_tool_icon()
            )
            actions.append({
                "command": f"/{t_name}",
                "title": t_title,
                "description": t_desc,
                "skill": skill_titles.get(skill_name, skill_name.capitalize()),
                "icon": icon,
                "tool_name": t_name,
                "skill_name": skill_name,
            })
    return actions


def _position_slash_popup(self):
    """Positionne le popup slash comme overlay flottant au-dessus du compositeur."""
    if not hasattr(self, 'composer') or not hasattr(self, 'panel') or not hasattr(self, 'slash_popup'):
        return
    # La hauteur du popup s'adapte exactement à son contenu (pas de marge vide)
    popup_h = self.slash_popup.content_height() if hasattr(self.slash_popup, 'content_height') else self.slash_popup.height()
    popup_w = self.composer.width()
    # Obtenir la position du compositeur par rapport au panel
    composer_pos = self.composer.mapTo(self.panel, self.composer.rect().topLeft())
    # Positionner juste au-dessus du compositeur
    x = composer_pos.x()
    y = composer_pos.y() - popup_h - 6
    y = max(38, y)  # ne pas sortir au-dessus du header
    self.slash_popup.setFixedWidth(popup_w)
    self.slash_popup.setFixedHeight(popup_h)
    self.slash_popup.move(x, y)
    self.slash_popup.raise_()


def _on_slash_triggered(self, query: str, slash_pos: int):
    """Appelé quand l'utilisateur tape '/' dans le champ de saisie."""
    if not self.slash_popup.all_actions:
        self.slash_popup.set_actions(self._build_slash_actions())

    has_results = self.slash_popup.filter_actions(query)
    if has_results or not query:
        self.slash_popup.show()
        self._update_height()
        self._position_slash_popup()
        self.slash_popup.raise_()
    else:
        self._on_slash_dismissed()


def _on_slash_dismissed(self):
    """Masque le popup overlay et restaure la hauteur de la fenêtre."""
    if self.slash_popup.isVisible():
        self.slash_popup.hide()
        self._update_height()


def _on_slash_action_selected(self, action: dict):
    """Appelé quand l'utilisateur sélectionne une action du menu slash."""
    tool_name = action.get("tool_name", "")
    skill_name = action.get("skill_name", "")

    # Remplacer le texte "/commande" par le prompt de la skill
    full_text = self.question.toPlainText()
    import re as _re
    cleaned = _re.sub(r'(?:^|\s)/\S*$', '', full_text).strip()

    self._select_skill_tool(skill_name, tool_name, cleaned)
    self._on_slash_dismissed()
