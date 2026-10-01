"""Nomenclature PNR : le repli réduit le bloc depuis le bas."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .pnr_bom_parser import parse_pnr_result, visible_nodes


class _LineTree(QTreeWidget):
    def drawBranches(self, painter, rect, index):
        pass


class PnrBomWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        self.tree = _LineTree(self)
        self.tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setItemsExpandable(False)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.tree, 0, Qt.AlignTop)
        self.tree.itemClicked.connect(self._toggle_item)
        self.tree.itemExpanded.connect(self._schedule_height)
        self.tree.itemCollapsed.connect(self._schedule_height)

    def set_result(self, result: str) -> None:
        data = parse_pnr_result(result)
        self.tree.clear()
        for section in data["sections"]:
            for node in visible_nodes(section):
                self._append_node(self.tree, node, "", is_root=True, is_last=True)
            for message in section["messages"]:
                QTreeWidgetItem(self.tree, [message])
        for message in data["messages"]:
            QTreeWidgetItem(self.tree, [message])
        self.tree.expandAll()
        self._update_height()
        self._schedule_height()

    def _toggle_item(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.childCount():
            item.setExpanded(not item.isExpanded())

    def _schedule_height(self, *_args) -> None:
        QTimer.singleShot(0, self._update_height)

    def _update_height(self) -> None:
        # Ne pas calculer à partir de visualItemRect : la position dépend
        # du défilement interne et peut créer un espace vide au repli.
        self.tree.executeDelayedItemsLayout()
        total = 0
        def add(item: QTreeWidgetItem) -> None:
            nonlocal total
            row_height = self.tree.sizeHintForIndex(self.tree.indexFromItem(item)).height()
            total += row_height if row_height > 0 else self.tree.fontMetrics().lineSpacing() + 6
            if item.isExpanded():
                for index in range(item.childCount()):
                    add(item.child(index))
        for index in range(self.tree.topLevelItemCount()):
            add(self.tree.topLevelItem(index))
        height = max(total, self.tree.fontMetrics().lineSpacing()) + 2 * self.tree.frameWidth() + 2
        self.tree.verticalScrollBar().setValue(0)
        self.tree.setFixedHeight(height)
        self.setFixedHeight(height)
        self.tree.updateGeometry()
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().invalidate()
            parent.updateGeometry()

    def _append_node(self, parent, node: dict, ancestor_prefix: str,
                     *, is_root: bool, is_last: bool) -> None:
        connector = "" if is_root else ("└─ " if is_last else "├─ ")
        item = QTreeWidgetItem(parent, [ancestor_prefix + connector + node["label"]])
        item.setToolTip(0, node["label"])
        if node["found"]:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        child_prefix = ancestor_prefix if is_root else ancestor_prefix + ("   " if is_last else "│  ")
        children = node["children"]
        for index, child in enumerate(children):
            self._append_node(item, child, child_prefix,
                              is_root=False, is_last=index == len(children) - 1)
