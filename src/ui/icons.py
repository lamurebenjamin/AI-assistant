# -*- coding: utf-8 -*-
"""Générateur et registre central des icônes SVG de l'application.

Toutes les icônes sont générées dynamiquement via ``create_svg_icon``
après la création de ``QApplication``. Les deux dicts ``ICONS`` (blanc,
fond sombre) et ``ICONS_DARK`` (noir, fond clair) sont synchronisés
et contiennent exactement les mêmes clés.

``ICON_LOGO_SVG`` contient le chemin SVG du logo étoile/fleur utilisé
comme fallback dans les headers quand ``assistant_icon.webp`` est absent.
Utiliser ``get_logo_pixmap(size)`` pour obtenir un ``QPixmap`` prêt à l'emploi.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

# ── Registres d'icônes ────────────────────────────────────────────────────────
ICONS: dict = {}
ICONS_DARK: dict = {}

# ── Logo SVG fallback (étoile / fleur) ───────────────────────────────────────
# Utilisé dans AssistantWindow, SettingsDialog, RecordingIndicator quand
# assistant_icon.webp est introuvable. Centralisé ici pour éviter la duplication.
ICON_LOGO_SVG = (
    '<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 '
    'C7.5 12.8 11.2 16.5 12 22.5 '
    'C12.8 16.5 16.5 12.8 22.5 12 '
    'C16.5 11.2 12.8 7.5 12 1.5z"/>'
)


def create_svg_icon(svg_path: str, color: str = "#FFFFFF", stroke_width: float = 2) -> QIcon:
    """Génère un QIcon à partir d'un chemin SVG avec couleur et épaisseur personnalisables."""
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


def get_logo_pixmap(size: int = 16, app_dir: str = "") -> QPixmap:
    """Retourne le pixmap du logo de l'application.

    Tente d'abord de charger ``assistant_icon.webp`` depuis ``app_dir``.
    En cas d'échec, génère le SVG fallback en blanc (adapté aux fonds sombres)
    ou en noir si ``size`` est négatif (convention interne non utilisée).

    Args:
        size: Taille du pixmap carré en pixels.
        app_dir: Répertoire contenant ``assistant_icon.webp``.

    Returns:
        Un ``QPixmap`` de ``size × size`` pixels.
    """
    if app_dir:
        path = os.path.join(app_dir, "assistant_icon.webp")
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap.scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
    # Fallback SVG
    icon = create_svg_icon(ICON_LOGO_SVG, "#FFFFFF")
    return icon.pixmap(size, size)


# ─────────────────────────────────────────────────────────────────────────────
#  Chemins SVG partagés (pour éviter la duplication dans initialize_icons)
# ─────────────────────────────────────────────────────────────────────────────
_SVG = {
    "add":        '<path d="M12 5v14M5 12h14"/>',
    "delete":     '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "up":         '<path d="M18 15l-6-6-6 6"/>',
    "down":       '<path d="M6 9l6 6 6-6"/>',
    "save":       '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    "cancel":     '<path d="M18 6L6 18M6 6l12 12"/>',
    "settings":   '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/>',
    "regenerate": '<path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6.7 6.7L4 9M20 15l-2.7 2.3A7 7 0 0 1 5.5 15"/>',
    # Icône moderne Feather/Lucide sans chevauchement interne.
    "copy":         '<rect width="13" height="13" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "check":        '<path d="M5 12.5l4.2 4.2L19 7"/>',
    "close":        '<path d="M6 6l12 12M18 6L6 18"/>',
    "speak":        '<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>',
    "speak_filled": '<path d="M11 5L6 9H2v6h4l5 4V5z" fill="#111111"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>',
    "stop":         '<rect x="6" y="6" width="12" height="12" rx="1"/>',
}

# Épaisseurs de trait spécifiques (dark only)
_DARK_STROKE = {
    "copy":         1.4,
    "check":        2.2,
    "close":        1.2,
    "speak":        1.6,
    "speak_filled": 2.0,
    "stop":         1.6,
}


def initialize_icons() -> None:
    """Initialise les dicts d'icônes après la création de QApplication.

    Utilise ``.clear() + .update()`` pour muter les objets dict existants
    plutôt que de les réassigner — tous les modules ayant fait
    ``from src.ui.icons import ICONS_DARK`` conservent leur référence.

    ``ICONS`` et ``ICONS_DARK`` contiennent exactement les mêmes clés.
    """
    light = {key: create_svg_icon(path) for key, path in _SVG.items()}
    dark = {
        key: create_svg_icon(path, "#111111", _DARK_STROKE.get(key, 2))
        for key, path in _SVG.items()
    }

    # Mutation en place — préserve les références capturées par les importeurs.
    ICONS.clear()
    ICONS.update(light)
    ICONS_DARK.clear()
    ICONS_DARK.update(dark)
