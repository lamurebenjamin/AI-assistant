"""Générateur et registre central des icônes SVG de l'application."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

ICONS = {}
ICONS_DARK = {}


def create_svg_icon(svg_path: str, color: str = "#FFFFFF", stroke_width: float = 2) -> QIcon:
    """Génère un QIcon à partir d'un chemin SVG avec couleur et épaisseur de trait personnalisables."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{svg_path}</svg>'
    )
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def initialize_icons() -> None:
    """Initialise le dictionnaire d'icônes après la création de QApplication."""
    global ICONS, ICONS_DARK
    ICONS = {
        "add": create_svg_icon('<path d="M12 5v14M5 12h14"/>'),
        "delete": create_svg_icon(
            '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        ),
        "up": create_svg_icon('<path d="M18 15l-6-6-6 6"/>'),
        "down": create_svg_icon('<path d="M6 9l6 6 6-6"/>'),
        "save": create_svg_icon(
            '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<path d="M17 21v-8H7v8M7 3v5h8"/>'
        ),
        "cancel": create_svg_icon('<path d="M18 6L6 18M6 6l12 12"/>'),
        "settings": create_svg_icon(
            '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/>'
        ),
        "regenerate": create_svg_icon(
            '<path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6.7 6.7L4 9M20 15l-2.7 2.3A7 7 0 0 1 5.5 15"/>'
        ),
        # Deux carrés symétriques autour du centre exact du viewBox 24 x 24.
        "copy": create_svg_icon(
            '<rect x="4" y="4" width="12" height="12" rx="2"/><rect x="8" y="8" width="12" height="12" rx="2"/>'
        ),
        "check": create_svg_icon('<path d="M5 12.5l4.2 4.2L19 7"/>'),
        "close": create_svg_icon('<path d="M6 6l12 12M18 6L6 18"/>'),
        "speak": create_svg_icon(
            '<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>'
        ),
        "stop": create_svg_icon('<rect x="6" y="6" width="12" height="12" rx="1"/>'),
    }
    ICONS_DARK = {
        "add": create_svg_icon('<path d="M12 5v14M5 12h14"/>', "#111111"),
        "delete": create_svg_icon(
            '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
            "#111111",
        ),
        "up": create_svg_icon('<path d="M18 15l-6-6-6 6"/>', "#111111"),
        "down": create_svg_icon('<path d="M6 9l6 6 6-6"/>', "#111111"),
        "save": create_svg_icon(
            '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<path d="M17 21v-8H7v8M7 3v5h8"/>',
            "#111111",
        ),
        "cancel": create_svg_icon('<path d="M18 6L6 18M6 6l12 12"/>', "#111111"),
        "copy": create_svg_icon(
            '<rect x="4" y="4" width="12" height="12" rx="2"/><rect x="8" y="8" width="12" height="12" rx="2"/>',
            "#111111",
            1.2,
        ),
        "check": create_svg_icon('<path d="M5 12.5l4.2 4.2L19 7"/>', "#111111", 2.2),
        "close": create_svg_icon('<path d="M6 6l12 12M18 6L6 18"/>', "#111111", 1.2),
        "speak": create_svg_icon(
            '<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>',
            "#111111",
            1.6,
        ),
        "stop": create_svg_icon('<rect x="6" y="6" width="12" height="12" rx="1"/>', "#111111", 1.6),
    }
