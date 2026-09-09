# -*- coding: utf-8 -*-
"""Composant de bloc de commandes Slash Command '/' pour filtrer et exécuter les skills."""

from typing import Any, Dict, List, Optional
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t


class SlashCommandItemWidget(QWidget):
    """Ligne représentant une action de skill dans le menu Slash Command."""

    def __init__(self, action: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.action = action
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Icône
        icon_label = QLabel(self.action.get("icon", "🔧"), self)
        icon_label.setStyleSheet("font-size: 14px; background: transparent;")
        icon_label.setFixedWidth(20)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label, 0, Qt.AlignVCenter)

        # Textes (Commande en haut, description en bas)
        text_col = QWidget(self)
        text_col.setStyleSheet("background: transparent;")
        col_layout = QVBoxLayout(text_col)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(1)

        cmd_color = "#E0E0E0" if t.is_dark_theme() else t.COLOR_PRIMARY
        cmd_label = QLabel(self.action.get("command", "/skill"), text_col)
        cmd_label.setStyleSheet(f"""
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_SM};
            font-weight: 700;
            color: {cmd_color};
            background: transparent;
        """)
        col_layout.addWidget(cmd_label)

        desc_label = QLabel(self.action.get("title", ""), text_col)
        desc_label.setStyleSheet(f"""
            font-family: {t.FONT_TEXT};
            font-size: {t.SIZE_XS};
            color: {t.COLOR_TEXT_SECONDARY};
            background: transparent;
        """)
        col_layout.addWidget(desc_label)
        layout.addWidget(text_col, 1, Qt.AlignVCenter)

        # Badge de skill
        skill_name = self.action.get("skill", "")
        if skill_name:
            badge = QLabel(skill_name, self)
            badge_bg = "rgba(255, 255, 255, 14)" if t.is_dark_theme() else t.COLOR_PRIMARY_LIGHT
            badge_fg = "#A0A0A0" if t.is_dark_theme() else t.COLOR_PRIMARY
            badge_border = "1px solid rgba(255, 255, 255, 22)" if t.is_dark_theme() else f"1px solid {t.COLOR_PRIMARY_BORDER}"
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {badge_bg};
                    color: {badge_fg};
                    border: {badge_border};
                    font-family: {t.FONT_TEXT};
                    font-size: 9px;
                    font-weight: 600;
                    border-radius: {t.RADIUS_SM};
                    padding: 2px 6px;
                }}
            """)
            layout.addWidget(badge, 0, Qt.AlignVCenter)


class SlashCommandPopup(QFrame):
    """Bloc de commandes slash intégré au-dessus du compositeur de message."""

    action_selected = pyqtSignal(dict)
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_actions: List[Dict[str, Any]] = []
        self.filtered_actions: List[Dict[str, Any]] = []
        self.setObjectName("SlashCommandPopup")
        # Activer le fond stylistique pour que border-radius clippe correctement le contenu
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()
        self.hide()

    def _build_ui(self):
        item_hover = "rgba(255, 255, 255, 16)" if t.is_dark_theme() else "rgba(37, 99, 184, 18)"
        item_selected = "rgba(255, 255, 255, 28)" if t.is_dark_theme() else "rgba(37, 99, 184, 35)"

        self.setStyleSheet(f"""
            QFrame#SlashCommandPopup {{
                background-color: {t.COLOR_BG_SURFACE};
                border: 1px solid {t.COLOR_BORDER};
                border-radius: {t.RADIUS_XL};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
                padding: 2px;
            }}
            QListWidget::item {{
                border-radius: 6px;
                margin: 1px 4px;
            }}
            QListWidget::item:hover {{
                background-color: {item_hover};
            }}
            QListWidget::item:selected {{
                background-color: {item_selected};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t.COLOR_SCROLLBAR_THUMB};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)

        # En-tête de section
        self.header_label = QLabel("COMMANDES SKILLS", self)
        self.header_label.setStyleSheet(f"""
            font-family: {t.FONT_TEXT};
            font-size: 9px;
            font-weight: 700;
            color: {t.COLOR_TEXT_MUTED};
            padding: 2px 8px;
            background: transparent;
        """)
        layout.addWidget(self.header_label)

        # Liste des résultats
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def set_actions(self, actions: List[Dict[str, Any]]):
        """Définit l'ensemble des actions de skills disponibles."""
        self.all_actions = list(actions)

    def filter_actions(self, query: str) -> bool:
        """Filtre les actions selon la chaîne saisie après '/'. Retourne True si des actions correspondent."""
        clean_query = query.strip().lower()
        if clean_query.startswith("/"):
            clean_query = clean_query[1:]

        if not clean_query:
            self.filtered_actions = list(self.all_actions)
        else:
            matches = []
            for item in self.all_actions:
                cmd = item.get("command", "").lower().lstrip("/")
                title = item.get("title", "").lower()
                skill = item.get("skill", "").lower()
                desc = item.get("description", "").lower()

                # Calcul du score de pertinence
                score = -1
                if cmd.startswith(clean_query):
                    score = 0
                elif skill.startswith(clean_query):
                    score = 1
                elif clean_query in cmd:
                    score = 2
                elif clean_query in title:
                    score = 3
                elif clean_query in skill:
                    score = 4
                elif clean_query in desc:
                    score = 5

                if score >= 0:
                    matches.append((score, item))

            matches.sort(key=lambda x: x[0])
            self.filtered_actions = [m[1] for m in matches]

        self._populate_list()
        return len(self.filtered_actions) > 0

    def content_height(self) -> int:
        """Retourne la hauteur exacte nécessaire pour afficher les éléments sans marge inutile."""
        count = len(self.filtered_actions)
        if count == 0:
            return 66
        item_height = 42
        display_count = min(5, count)
        return display_count * (item_height + 2) + 34

    def sizeHint(self) -> QSize:
        return QSize(self.width() if self.width() > 0 else 300, self.content_height())

    def _populate_list(self):
        self.list_widget.clear()
        if not self.filtered_actions:
            empty_item = QListWidgetItem("Aucune action trouvée")
            empty_item.setFlags(Qt.NoItemFlags)
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.list_widget.addItem(empty_item)
            self.setFixedHeight(self.content_height())
            return

        item_height = 42
        for action in self.filtered_actions:
            list_item = QListWidgetItem(self.list_widget)
            list_item.setSizeHint(QSize(0, item_height))
            widget = SlashCommandItemWidget(action, self)
            self.list_widget.setItemWidget(list_item, widget)

        self.list_widget.setCurrentRow(0)
        self.setFixedHeight(self.content_height())

    def navigate(self, key: int) -> bool:
        """Déplace la sélection vers le haut ou le bas."""
        count = self.list_widget.count()
        if count <= 0 or not self.filtered_actions:
            return False

        current = self.list_widget.currentRow()
        if key == Qt.Key_Down:
            next_row = (current + 1) % count
            self.list_widget.setCurrentRow(next_row)
            return True
        elif key == Qt.Key_Up:
            prev_row = (current - 1 + count) % count
            self.list_widget.setCurrentRow(prev_row)
            return True
        return False

    def select_current(self) -> bool:
        """Valide l'élément actuellement sélectionné."""
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.filtered_actions):
            action = self.filtered_actions[row]
            self.hide()
            self.action_selected.emit(action)
            return True
        return False

    def _on_item_clicked(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        if 0 <= row < len(self.filtered_actions):
            action = self.filtered_actions[row]
            self.hide()
            self.action_selected.emit(action)

    def reposition_above(self, target_widget=None):
        """Méthode conservée pour compatibilité ; le placement est géré par le layout."""
        pass
