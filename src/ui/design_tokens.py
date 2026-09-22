# -*- coding: utf-8 -*-
"""Tokens de design centralisés pour l'application Assistant IA.

Ce module est la source de vérité unique pour toutes les valeurs
visuelles : couleurs, typographies, espacements et rayons.
Prend en charge le thème clair et le thème sombre Antigravity.

Les dimensions UI communes sont également définies ici. Les nouveaux widgets
doivent réutiliser ces constantes plutôt que de créer des valeurs locales.
"""

import sys

THEME_DARK = {
    # ── Neutrals / Texte ─────────────────────────────────────────────────────────
    "COLOR_TEXT_PRIMARY": "#E0E0E0",      # Texte principal Antigravity
    "COLOR_TEXT_ACTIVE": "#FFFFFF",       # Texte et icônes des éléments actifs
    "COLOR_TEXT_SECONDARY": "#9D9D9D",    # Sous-labels, secondaire
    "COLOR_TEXT_MUTED": "#6E7681",        # Désactivé, placeholder
    "COLOR_TEXT_INVERSE": "#111111",      # Texte sur fond clair inversé
    "COLOR_TEXT_LINK": "#58A6FF",
    "COLOR_TEXT_CODE": "#E0E0E0",

    # ── Backgrounds ──────────────────────────────────────────────────────────────
    "COLOR_BG_PAGE": "#1E1E1E",           # Fond fenêtres opaques (VS Code / Antigravity)
    "COLOR_BG_SURFACE": "#252526",        # Fond champs, cards, menus
    "COLOR_BG_SUBTLE": "#2A2D2E",         # Alternance, hover léger
    "COLOR_BG_ACRYLIC": "rgba(30, 30, 30, 88)",  # Panneau translucide sombre
    "COLOR_BORDER_ACRYLIC": "rgba(255, 255, 255, 30)", # Bordure panneau translucide

    # ── Borders ──────────────────────────────────────────────────────────────────
    "COLOR_BORDER": "#3C3C3C",            # Bordure standard Antigravity
    "COLOR_BORDER_STRONG": "#0078D4",     # Focus / hover accent
    "COLOR_BORDER_SUBTLE": "#2D2D2D",     # Bordure très légère
    "COLOR_BORDER_INPUT": "#3C3C3C",      # Bordure champs de saisie
    "COLOR_SEPARATOR": "rgba(255, 255, 255, 25)",

    # ── Brand / Primary (Bleu Antigravity) ───────────────────────────────────────
    "COLOR_PRIMARY": "#0078D4",           # Bleu principal
    "COLOR_PRIMARY_HOVER": "#1E88E5",     # Hover bouton principal
    "COLOR_PRIMARY_ACTIVE": "#005A9E",    # Pressed bouton principal
    "COLOR_PRIMARY_LIGHT": "#2A2D2E",     # Fond bulle user (gris sombre différencié)
    "COLOR_PRIMARY_BORDER": "#4A4A4A",    # Bordure bulle user (gris moyen)
    "COLOR_PRIMARY_SUBTLE": "rgba(56, 139, 253, 35)", # Survol léger zone bleue
    "COLOR_CODE_BACKGROUND": "rgba(255, 255, 255, 18)",
    "COLOR_ERROR_BACKGROUND": "rgba(209, 52, 56, 0.10)",
    "COLOR_ERROR_BORDER": "rgba(209, 52, 56, 0.40)",
    "COLOR_OVERLAY_HOVER": "rgba(255, 255, 255, 16)",
    "COLOR_OVERLAY_SELECTED": "rgba(255, 255, 255, 28)",
    "COLOR_TOOL_MUTED": "#8B949E",
    "COLOR_TOOL_TEXT": "#C9D1D9",
    "COLOR_TOOL_CODE_BACKGROUND": "rgba(0, 0, 0, 45)",
    "COLOR_TOOL_CODE_BORDER": "rgba(255, 255, 255, 14)",
    "COLOR_COMPOSER_BACKGROUND": "rgba(37, 37, 38, 220)",
    "COLOR_PREVIEW_BACKGROUND": "rgba(45, 45, 45, 180)",
    "COLOR_RECORDING_BACKGROUND": "rgba(198, 40, 40, 35)",
    "COLOR_NAVIGATION_HOVER": "rgba(128, 128, 128, 70)",
    "COLOR_STATUS_SUBTLE": "#555555",
    "COLOR_SKILL_BACKGROUND": "rgba(37, 99, 184, 18)",
    "COLOR_SKILL_TEXT": "#79B8FF",
    "COLOR_INLINE_EDIT_HOVER": "rgba(255, 255, 255, 175)",
    "COLOR_INLINE_EDIT_BORDER": "rgba(0, 0, 0, 45)",
    "COLOR_INLINE_EDIT_FOCUS": "rgba(0, 0, 0, 70)",
    "COLOR_SCROLLBAR_HORIZONTAL": "rgba(82, 91, 102, 115)",
    "COLOR_PREVIEW_DASHED": "rgba(128, 128, 128, 25)",

    # ── Success / Vert ───────────────────────────────────────────────────────────
    "COLOR_SUCCESS": "#4EC9B0",           # Succès / points de pensée
    "COLOR_SUCCESS_LIGHT": "#252526",     # Fond bulle assistant (gris sombre Antigravity)
    "COLOR_SUCCESS_BORDER": "#3C3C3C",    # Bordure bulle assistant (neutre)
    "COLOR_SUCCESS_TEXT": "#CCCCCC",      # Texte dans bulle assistant
    "COLOR_SUCCESS_STRONG": "#4EC9B0",    # Badge succès fort

    # ── User bubble text ─────────────────────────────────────────────────────────
    "COLOR_USER_TEXT": "#F1F5F9",         # Texte dans bulle utilisateur

    # ── Danger / Erreur ──────────────────────────────────────────────────────────
    "COLOR_DANGER": "#F14C4C",            # Erreur, bouton destructeur
    "COLOR_DANGER_ALT": "#E03E3E",        # Variante danger
    "COLOR_WARNING": "#CCA700",           # Avertissement

    # ── Interactive overlays ─────────────────────────────────────────────────────
    "COLOR_HOVER_DARK": "rgba(255, 255, 255, 22)",     # Survol sur fond sombre
    "COLOR_PRESS_DARK": "rgba(255, 255, 255, 45)",     # Press sur fond sombre
    "COLOR_HOVER_LIGHT": "rgba(255, 255, 255, 34)",
    "COLOR_PRESS_LIGHT": "rgba(255, 255, 255, 60)",

    # ── Scrollbar ────────────────────────────────────────────────────────────────
    "COLOR_SCROLLBAR_TRACK": "transparent",
    "COLOR_SCROLLBAR_THUMB": "rgba(121, 121, 121, 100)",
    "COLOR_SCROLLBAR_HOVER": "rgba(160, 160, 160, 150)",

    # ── Audio bars ───────────────────────────────────────────────────────────────
    "COLOR_AUDIO_ACTIVE": "#388BFD",
    "COLOR_AUDIO_IDLE": "#6E7681",
}

THEME_LIGHT = {
    # ── Neutrals / Texte ─────────────────────────────────────────────────────────
    "COLOR_TEXT_PRIMARY": "#111111",
    "COLOR_TEXT_ACTIVE": "#111111",
    "COLOR_TEXT_SECONDARY": "#4B5563",
    "COLOR_TEXT_MUTED": "#8A949F",
    "COLOR_TEXT_INVERSE": "#FFFFFF",
    "COLOR_TEXT_LINK": "#1565C0",
    "COLOR_TEXT_CODE": "#111111",

    # ── Backgrounds ──────────────────────────────────────────────────────────────
    "COLOR_BG_PAGE": "#F8FAFC",
    "COLOR_BG_SURFACE": "#FFFFFF",
    "COLOR_BG_SUBTLE": "#F1F5F9",
    "COLOR_BG_ACRYLIC": "rgba(248, 250, 252, 110)",
    "COLOR_BORDER_ACRYLIC": "rgba(0, 0, 0, 35)",

    # ── Borders ──────────────────────────────────────────────────────────────────
    "COLOR_BORDER": "#CBD7E4",
    "COLOR_BORDER_STRONG": "#AAB8C7",
    "COLOR_BORDER_SUBTLE": "#DDE6F0",
    "COLOR_BORDER_INPUT": "rgba(8,74,144,70)",
    "COLOR_SEPARATOR": "rgba(0, 0, 0, 25)",

    # ── Brand / Primary (bleu) ───────────────────────────────────────────────────
    "COLOR_PRIMARY": "#2563B8",
    "COLOR_PRIMARY_HOVER": "#1D4F96",
    "COLOR_PRIMARY_ACTIVE": "#173F78",
    "COLOR_PRIMARY_LIGHT": "#DCEBFF",
    "COLOR_PRIMARY_BORDER": "#B7D3F7",
    "COLOR_PRIMARY_SUBTLE": "rgba(37,99,184,18)",
    "COLOR_CODE_BACKGROUND": "rgba(0, 0, 0, 18)",
    "COLOR_ERROR_BACKGROUND": "rgba(198, 40, 40, 0.10)",
    "COLOR_ERROR_BORDER": "rgba(198, 40, 40, 0.40)",
    "COLOR_OVERLAY_HOVER": "rgba(37, 99, 184, 18)",
    "COLOR_OVERLAY_SELECTED": "rgba(37, 99, 184, 35)",
    "COLOR_TOOL_MUTED": "#656D76",
    "COLOR_TOOL_TEXT": "#24292F",
    "COLOR_TOOL_CODE_BACKGROUND": "rgba(0, 0, 0, 6)",
    "COLOR_TOOL_CODE_BORDER": "rgba(0, 0, 0, 15)",
    "COLOR_COMPOSER_BACKGROUND": "#FFFFFF",
    "COLOR_PREVIEW_BACKGROUND": "#F1F5F9",
    "COLOR_RECORDING_BACKGROUND": "rgba(198, 40, 40, 35)",
    "COLOR_NAVIGATION_HOVER": "rgba(128, 128, 128, 70)",
    "COLOR_STATUS_SUBTLE": "#52677C",
    "COLOR_SKILL_BACKGROUND": "rgba(37, 99, 184, 18)",
    "COLOR_SKILL_TEXT": "#245A91",
    "COLOR_INLINE_EDIT_HOVER": "rgba(255, 255, 255, 175)",
    "COLOR_INLINE_EDIT_BORDER": "rgba(0, 0, 0, 45)",
    "COLOR_INLINE_EDIT_FOCUS": "rgba(0, 0, 0, 70)",
    "COLOR_SCROLLBAR_HORIZONTAL": "rgba(82, 91, 102, 115)",
    "COLOR_PREVIEW_DASHED": "rgba(128, 128, 128, 25)",

    # ── Success / Vert ───────────────────────────────────────────────────────────
    "COLOR_SUCCESS": "#397D58",
    "COLOR_SUCCESS_LIGHT": "#EFF9F2",
    "COLOR_SUCCESS_BORDER": "#C9E8D3",
    "COLOR_SUCCESS_TEXT": "#183B28",
    "COLOR_SUCCESS_STRONG": "#16833B",

    # ── User bubble text ─────────────────────────────────────────────────────────
    "COLOR_USER_TEXT": "#17324D",

    # ── Danger / Erreur ──────────────────────────────────────────────────────────
    "COLOR_DANGER": "#C62828",
    "COLOR_DANGER_ALT": "#D13438",
    "COLOR_WARNING": "#C47F00",

    # ── Interactive overlays ─────────────────────────────────────────────────────
    "COLOR_HOVER_DARK": "rgba(0,0,0,18)",
    "COLOR_PRESS_DARK": "rgba(0,0,0,35)",
    "COLOR_HOVER_LIGHT": "rgba(255,255,255,34)",
    "COLOR_PRESS_LIGHT": "rgba(255,255,255,60)",

    # ── Scrollbar ────────────────────────────────────────────────────────────────
    "COLOR_SCROLLBAR_TRACK": "rgba(0,0,0,14)",
    "COLOR_SCROLLBAR_THUMB": "rgba(30,30,30,85)",
    "COLOR_SCROLLBAR_HOVER": "rgba(30,30,30,135)",

    # ── Audio bars ───────────────────────────────────────────────────────────────
    "COLOR_AUDIO_ACTIVE": "#0A68D8",
    "COLOR_AUDIO_IDLE": "#8993A0",
}

CURRENT_THEME = "dark"

# Initialisation des variables de module avec THEME_DARK par défaut
for _k, _v in THEME_DARK.items():
    globals()[_k] = _v


def set_active_theme(theme_name: str) -> None:
    """Bascule le thème actif ('dark' ou 'light') et met à jour toutes les constantes."""
    global CURRENT_THEME
    clean_name = "dark" if theme_name.lower().startswith("dark") else "light"
    CURRENT_THEME = clean_name
    palette = THEME_DARK if clean_name == "dark" else THEME_LIGHT

    mod = sys.modules[__name__]
    for key, val in palette.items():
        setattr(mod, key, val)
        globals()[key] = val


def is_dark_theme() -> bool:
    """Retourne True si le thème sombre est actif."""
    return CURRENT_THEME == "dark"


# ── Constantes invariantes (Typographies, rayons, espacements) ────────────────
RADIUS_XS   = "3px"    # Tags, petits badges
RADIUS_SM   = "4px"    # Champs, items de liste, scrollbar thumb
RADIUS_MD   = "6px"    # Boutons standard, scrollbar track
RADIUS_LG   = "8px"    # Boutons CTA, onglets, panneaux internes
RADIUS_XL   = "14px"   # Bulles de chat, boutons icônes, zoom loupe
RADIUS_2XL  = "8px"    # Panneaux acrylic : même palier que LG (contrainte DWM)

FONT_DISPLAY = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"
FONT_TEXT    = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"
FONT_MENU    = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"

SIZE_XS  = "11px"   # Métadonnées, annotations
SIZE_SM  = "12px"   # Labels compacts
SIZE_MD  = "14px"   # Corps de texte, bulles, menus
SIZE_LG  = "14px"   # UI standard ; égal à SIZE_MD volontairement (charte 14px)
SIZE_XL  = "16px"   # Titres de section importants

SPACING_XS  = 3
SPACING_SM  = 6
SPACING_MD  = 9
SPACING_LG  = 12
SPACING_XL  = 16

# ── Dimensions UI communes ───────────────────────────────────────────────────
HEADER_HEIGHT         = 36   # Hauteur des barres de titre
BUTTON_SIZE_HEADER    = 28   # Bouton carré des barres de titre
BUTTON_HOVER_DIAMETER = 26   # Cercle de survol des boutons
ICON_SIZE_HEADER      = 16   # Icône logo dans le header
ICON_SIZE_BUTTON      = 18   # Icône standard des boutons de fenêtre
ICON_SIZE_CLOSE       = 14   # Icône de fermeture, alignée sur le bouton micro
ICON_SIZE_COPY        = 17   # Icône copier/check
ICON_SIZE_COMPOSER    = 14   # Icône dans le compositeur
COMPOSER_HEIGHT       = 30   # Hauteur du champ de message
COMPOSER_TEXT_PADDING  = 5   # Padding vertical du texte du compositeur
ICON_STROKE_WIDTH     = 1.3  # Épaisseur standard des icônes de boutons
HEADER_ROW_HEIGHT     = 24   # Hauteur des en-têtes pliables
ICON_SIZE_TIMELINE    = 16   # Icône d'une étape d'outil
TIMELINE_LINE_WIDTH   = 1    # Ligne verticale de la timeline
ICON_SIZE_THINKING    = 14   # Icône du bloc de raisonnement
TIMELINE_INDENT       = 10   # Retrait du contenu sous l'en-tête d'un groupe
CHAT_BUBBLE_PADDING_X = 10
CHAT_BUBBLE_PADDING_Y = 8
AUDIO_BARS_WIDTH      = 106
RECORDING_INDICATOR_WIDTH = 240
AUDIO_BARS_HEIGHT     = 24
DOCUMENT_PREVIEW_HEIGHT = 130
DOCUMENT_THUMBNAIL_WIDTH = 76
DOCUMENT_THUMBNAIL_HEIGHT = 76
HEADER_MARGIN_LEFT = 9
HEADER_MARGIN_TOP = 1
HEADER_MARGIN_RIGHT = 3
HEADER_MARGIN_RIGHT_CENTERED = 9
HEADER_SPACING = 3
HEADER_SPACING_CENTERED = 7
SEPARATOR_INSET = 12
SEPARATOR_INSET_COMPACT = 14
HAIRLINE_HEIGHT = 1
ICON_SIZE_SKILL = 20
ICON_SIZE_DIALOG = 16
INPUT_HEIGHT = 34
SCROLLBAR_WIDTH = 6
SCROLLBAR_THUMB_MIN = 26
SPINBOX_BUTTON_WIDTH = 18
ACRYLIC_NATIVE_DARK = 0x8C1E1E1E
ACRYLIC_NATIVE_LIGHT = 0x98F8F8F8
