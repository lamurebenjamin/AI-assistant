"""Grille de cartes FTNC du suivi Excel, sans défilement interne."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # Le plugin Qt SVG peut être absent de certaines installations.
    QSvgRenderer = None


CARD_MAX_WIDTH = 180
CARD_GAP = 8
PLANNER_ICON = Path(__file__).resolve().parents[3] / 'skills' / 'ftnc' / 'planner.svg'


class FtncCardsWidget(QWidget):
    toggled = Signal()

    def __init__(self, parent=None, font_size_offset=0):
        super().__init__(parent)
        self.font_size_offset = font_size_offset
        self.setObjectName('FtncCardsWidget')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(CARD_GAP)
        self._layout.setAlignment(Qt.AlignTop)
        self._cards = []
        self._grid = None
        self._columns = 0

    def _label(self, text, parent, bold=False):
        label = QLabel(str(text), parent)
        label.setTextFormat(Qt.PlainText)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        font = label.font()
        font.setBold(bold)
        if self.font_size_offset and font.pointSize() > 0:
            font.setPointSize(max(7, font.pointSize() + self.font_size_offset))
        label.setFont(font)
        return label

    def refresh_theme(self):
        for card in self._cards:
            self._style_card(card)

    def _style_card(self, card):
        palette = self.palette()
        from PySide6.QtGui import QPalette
        bg = palette.color(QPalette.Base).name()
        border = palette.color(QPalette.Mid).name()
        card.setStyleSheet('QFrame#FtncCard { background-color: ' + bg
                           + '; border: 1px solid ' + border + '; border-radius: 8px; }'
                           'QFrame#FtncCard QLabel, QFrame#FtncCard QPushButton {'
                           ' background: transparent; border: none; }')

    def _planner_pixmap(self):
        if not PLANNER_ICON.is_file():
            return QPixmap()
        if QSvgRenderer is not None:
            renderer = QSvgRenderer(str(PLANNER_ICON))
            if renderer.isValid():
                pixmap = QPixmap(16, 16)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap
        return QIcon(str(PLANNER_ICON)).pixmap(16, 16)

    def set_result(self, result, tool_name, cards_data=None, error='',
                   missing_planner=None, missing_error=''):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards = []
        self._grid = None
        self._columns = 0
        if error:
            self._layout.addWidget(self._label('Suivi FTNC indisponible : ' + error, self))
        elif cards_data is None:
            self._layout.addWidget(self._label('Données du suivi FTNC indisponibles.', self))
        elif not cards_data:
            self._layout.addWidget(self._label('Aucune FTNC correspondante dans le suivi €uro.', self))
        else:
            self._layout.addWidget(self._label('FTNC du suivi €uro', self, True))
            grid_holder = QWidget(self)
            grid_holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            self._grid = QGridLayout(grid_holder)
            self._grid.setContentsMargins(0, 0, 0, 0)
            self._grid.setHorizontalSpacing(CARD_GAP)
            self._grid.setVerticalSpacing(CARD_GAP)
            self._grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            for data in cards_data:
                self._cards.append(self._card(data, grid_holder))
            self._layout.addWidget(grid_holder)
            self._reflow(force=True)
        if missing_planner:
            self._layout.addWidget(self._label(
                "Présentes dans le planner, mais absentes du suivi €uro filtré : "
                + ", ".join(missing_planner), self))
        if missing_error:
            self._layout.addWidget(self._label(
                "Comparaison avec le planner indisponible : " + missing_error, self))
        self.updateGeometry()

    def _card(self, data, parent):
        frame = QFrame(parent)
        frame.setObjectName('FtncCard')
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self._style_card(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        header = QWidget(frame)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        reference = self._label(data.get('reference') or 'Référence non renseignée', header, True)
        row.addWidget(reference, 1)
        if data.get('sur_planner'):
            pixmap = self._planner_pixmap()
            if not pixmap.isNull():
                icon = QLabel(header)
                icon.setPixmap(pixmap)
                icon.setFixedSize(16, 16)
                icon.setToolTip('Présente dans le planner')
                row.addWidget(icon, 0, Qt.AlignTop)
        layout.addWidget(header)
        layout.addWidget(self._label(data.get('programme') or 'Programme non renseigné', frame))
        layout.addWidget(self._label('Pièces : ' + (data.get('quantite') or 'Non renseigné'), frame))
        fields = [('statut', 'Statut'), ('type', 'Type'), ('pole', 'Pôle'),
                  ('piece', 'Pièce'), ('reference_piece', 'Référence pièce'),
                  ('date_debut', 'Date de début'), ('description', 'Description')]
        details = '\n'.join(label + ' : ' + str(data[key])
                            for key, label in fields if data.get(key))
        if details:
            button = QPushButton('Afficher les détails', frame)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.StrongFocus)
            layout.addWidget(button)
            extra = self._label(details, frame)
            extra.hide()
            layout.addWidget(extra)

            def toggle():
                expanded = extra.isHidden()
                extra.setVisible(expanded)
                button.setText('Masquer les détails' if expanded else 'Afficher les détails')
                self.updateGeometry()
                self.toggled.emit()

            button.clicked.connect(toggle)
        return frame

    def _reflow(self, force=False):
        if self._grid is None:
            return
        available = max(1, self.width())
        columns = max(1, (available + CARD_GAP) // (CARD_MAX_WIDTH + CARD_GAP))
        if not force and columns == self._columns:
            return
        self._columns = columns
        while self._grid.count():
            self._grid.takeAt(0)
        card_width = min(CARD_MAX_WIDTH, available)
        for index, card in enumerate(self._cards):
            card.setFixedWidth(card_width)
            self._grid.addWidget(card, index // columns, index % columns, Qt.AlignTop)
        self._grid.invalidate()
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()


def add_ftnc_cards(layout, parent, width, font_offset, result, tool_name,
                   toggled, cards_data=None, error='', missing_planner=None,
                   missing_error=''):
    cards = FtncCardsWidget(parent, font_offset)
    cards.setFixedWidth(width)
    cards.set_result(result, tool_name, cards_data, error,
                     missing_planner, missing_error)
    cards.toggled.connect(toggled)
    layout.addWidget(cards, 0, Qt.AlignLeft)
