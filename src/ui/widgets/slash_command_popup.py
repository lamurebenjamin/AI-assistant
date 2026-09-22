# -*- coding: utf-8 -*-
"""Composant de bloc de commandes Slash Command '/' pour filtrer et exécuter les skills."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t
from src.ui.icons import get_file_type_icon
from src.ui.stylesheet import (
    qss_slash_command_label,
    qss_slash_description,
    qss_slash_header,
    qss_slash_popup,
    qss_transparent_surface,
)


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
        icon_label = QLabel(self)
        icon = self.action.get("icon") or get_file_type_icon("txt")
        if isinstance(icon, QIcon):
            # Keep the icon transparent and large enough to remain legible in
            # the compact row without stretching it.
            icon_label.setPixmap(icon.pixmap(QSize(24, 24), QIcon.Normal, QIcon.On))
        else:
            icon_label.setText("")
            icon_label.setStyleSheet("font-size: 14px; " + qss_transparent_surface())
        icon_label.setFixedSize(26, 26)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(qss_transparent_surface())
        layout.addWidget(icon_label, 0, Qt.AlignVCenter)

        # Textes (Commande en haut, description en bas)
        text_col = QWidget(self)
        text_col.setStyleSheet(qss_transparent_surface())
        col_layout = QVBoxLayout(text_col)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(1)

        command = self.action.get("command", "skill").lstrip("/")
        skill_name = self.action.get("skill", "").strip()
        command_label = f"{skill_name} - {command}" if skill_name else command
        cmd_label = QLabel(command_label, text_col)
        cmd_label.setStyleSheet(qss_slash_command_label())
        col_layout.addWidget(cmd_label)

        self.desc_label = DescriptionTicker(
            self.action.get("description") or self.action.get("title", ""),
            text_col,
        )
        self.desc_label.setStyleSheet(qss_slash_description())
        col_layout.addWidget(self.desc_label)
        layout.addWidget(text_col, 1, Qt.AlignVCenter)

class DescriptionTicker(QLabel):
    """Description sur une ligne, défilant lorsqu'elle dépasse l'espace disponible."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._offset = 0
        self._scrolling_requested = False
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._scroll)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setToolTip(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._offset = 0
        self._timer.stop()
        if self._scrolling_requested:
            self._start_timer_if_needed()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.stop()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def start_scrolling(self):
        self._scrolling_requested = True
        self._start_timer_if_needed()

    def _start_timer_if_needed(self):
        if self.fontMetrics().horizontalAdvance(self.text()) > self.width():
            self._timer.start()

    def stop_scrolling(self):
        self._scrolling_requested = False
        self._timer.stop()
        self._offset = 0
        self.update()

    def _scroll(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        if text_width <= self.width():
            self._timer.stop()
            self._offset = 0
        else:
            self._offset = (self._offset + 1) % (text_width + self.width() // 2)
        self.update()

    def paintEvent(self, event):
        if self.fontMetrics().horizontalAdvance(self.text()) <= self.width():
            super().paintEvent(event)
            return

        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setClipRect(self.rect())
        y = (self.height() + self.fontMetrics().ascent() - self.fontMetrics().descent()) // 2
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        gap = max(24, self.width() // 2)
        x = -self._offset
        painter.drawText(x, y, self.text())
        if x + text_width < self.width():
            painter.drawText(x + text_width + gap, y, self.text())


class SlashCommandPopup(QFrame):
    """Bloc de commandes slash intégré au-dessus du compositeur de message."""

    action_selected = Signal(dict)
    dismissed = Signal()

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
        self.setStyleSheet(qss_slash_popup())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)

        # En-tête de section
        self.header_label = QLabel("Skills", self)
        self.header_label.setStyleSheet(qss_slash_header())
        layout.addWidget(self.header_label)

        # Liste des résultats
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.currentRowChanged.connect(self._update_selected_description)
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
        self._update_selected_description(0)
        self.setFixedHeight(self.content_height())

    def _update_selected_description(self, row: int):
        """Anime uniquement la description de la ligne actuellement sélectionnée."""
        for index in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(index))
            if widget is None or not hasattr(widget, "desc_label"):
                continue
            if index == row:
                widget.desc_label.start_scrolling()
            else:
                widget.desc_label.stop_scrolling()

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
