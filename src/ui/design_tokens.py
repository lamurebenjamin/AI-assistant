# -*- coding: utf-8 -*-
"""Tokens de design centralisés pour l'application Assistant IA.

Ce module est la source de vérité unique pour toutes les valeurs
visuelles : couleurs, typographies, espacements et rayons.
Prend en charge le thème clair et le thème sombre Antigravity.
"""

import sys

THEME_DARK = {
    # ── Neutrals / Texte ─────────────────────────────────────────────────────────
    "COLOR_TEXT_PRIMARY": "#E0E0E0",      # Texte principal Antigravity
    "COLOR_TEXT_SECONDARY": "#9D9D9D",    # Sous-labels, secondaire
    "COLOR_TEXT_MUTED": "#6E7681",        # Désactivé, placeholder
    "COLOR_TEXT_INVERSE": "#111111",      # Texte sur fond clair inversé

    # ── Backgrounds ──────────────────────────────────────────────────────────────
    "COLOR_BG_PAGE": "#1E1E1E",           # Fond fenêtres opaques (VS Code / Antigravity)
    "COLOR_BG_SURFACE": "#252526",        # Fond champs, cards, menus
    "COLOR_BG_SUBTLE": "#2A2D2E",         # Alternance, hover léger
    "COLOR_BG_ACRYLIC": "rgba(30, 30, 30, 225)",  # Panneau translucide sombre
    "COLOR_BORDER_ACRYLIC": "rgba(255, 255, 255, 30)", # Bordure panneau translucide

    # ── Borders ──────────────────────────────────────────────────────────────────
    "COLOR_BORDER": "#3C3C3C",            # Bordure standard Antigravity
    "COLOR_BORDER_STRONG": "#0078D4",     # Focus / hover accent
    "COLOR_BORDER_SUBTLE": "#2D2D2D",     # Bordure très légère
    "COLOR_BORDER_INPUT": "#3C3C3C",      # Bordure champs de saisie

    # ── Brand / Primary (Bleu Antigravity) ───────────────────────────────────────
    "COLOR_PRIMARY": "#0078D4",           # Bleu principal
    "COLOR_PRIMARY_HOVER": "#1E88E5",     # Hover bouton principal
    "COLOR_PRIMARY_ACTIVE": "#005A9E",    # Pressed bouton principal
    "COLOR_PRIMARY_LIGHT": "#2A2D2E",     # Fond bulle user (gris sombre différencié)
    "COLOR_PRIMARY_BORDER": "#4A4A4A",    # Bordure bulle user (gris moyen)
    "COLOR_PRIMARY_SUBTLE": "rgba(56, 139, 253, 35)", # Survol léger zone bleue

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

    # ── Palette étendue (dialogs, listes) ────────────────────────────────────────
    "COLOR_GRAY_100": "#2D2D2D",
    "COLOR_GRAY_200": "#252526",
    "COLOR_GRAY_300": "#1E1E1E",
    "COLOR_GRAY_500": "#858585",
    "COLOR_GRAY_600": "#9D9D9D",
    "COLOR_GRAY_700": "#CCCCCC",

    # ── Audio bars ───────────────────────────────────────────────────────────────
    "COLOR_AUDIO_ACTIVE": "#388BFD",
    "COLOR_AUDIO_IDLE": "#6E7681",
}

THEME_LIGHT = {
    # ── Neutrals / Texte ─────────────────────────────────────────────────────────
    "COLOR_TEXT_PRIMARY": "#111111",
    "COLOR_TEXT_SECONDARY": "#4B5563",
    "COLOR_TEXT_MUTED": "#8A949F",
    "COLOR_TEXT_INVERSE": "#FFFFFF",

    # ── Backgrounds ──────────────────────────────────────────────────────────────
    "COLOR_BG_PAGE": "#F8FAFC",
    "COLOR_BG_SURFACE": "#FFFFFF",
    "COLOR_BG_SUBTLE": "#F1F5F9",
    "COLOR_BG_ACRYLIC": "rgba(248, 250, 252, 248)",
    "COLOR_BORDER_ACRYLIC": "rgba(0, 0, 0, 35)",

    # ── Borders ──────────────────────────────────────────────────────────────────
    "COLOR_BORDER": "#CBD7E4",
    "COLOR_BORDER_STRONG": "#AAB8C7",
    "COLOR_BORDER_SUBTLE": "#DDE6F0",
    "COLOR_BORDER_INPUT": "rgba(8,74,144,70)",

    # ── Brand / Primary (bleu) ───────────────────────────────────────────────────
    "COLOR_PRIMARY": "#2563B8",
    "COLOR_PRIMARY_HOVER": "#1D4F96",
    "COLOR_PRIMARY_ACTIVE": "#173F78",
    "COLOR_PRIMARY_LIGHT": "#DCEBFF",
    "COLOR_PRIMARY_BORDER": "#B7D3F7",
    "COLOR_PRIMARY_SUBTLE": "rgba(37,99,184,18)",

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

    # ── Palette étendue (dialogs, listes) ────────────────────────────────────────
    "COLOR_GRAY_100": "#EEF3F8",
    "COLOR_GRAY_200": "#E9EEF4",
    "COLOR_GRAY_300": "#E6EDF4",
    "COLOR_GRAY_500": "#747B84",
    "COLOR_GRAY_600": "#5E6670",
    "COLOR_GRAY_700": "#52677C",

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
RADIUS_2XL  = "16px"   # Panneaux principaux (acrylic), header badge

FONT_DISPLAY = "'Aptos Display','Segoe UI Variable Display','Segoe UI',Arial"
FONT_TEXT    = "'Aptos','Segoe UI Variable Text','Segoe UI',Arial"
FONT_MENU    = "'Segoe UI Variable','Segoe UI',Arial"

SIZE_XS  = "10px"   # Métadonnées, annotations
SIZE_SM  = "11px"   # Labels compacts
SIZE_MD  = "12px"   # Corps de texte, bulles, menus
SIZE_LG  = "13px"   # UI standard (boutons, labels, champs)
SIZE_XL  = "15px"   # Titres de section importants

SPACING_XS  = 3
SPACING_SM  = 6
SPACING_MD  = 9
SPACING_LG  = 12
SPACING_XL  = 16

HEADER_HEIGHT        = 36    # Hauteur de la barre de titre
ICON_SIZE_HEADER     = 18    # Icône logo dans le header
ICON_SIZE_BUTTON     = 19    # Icône dans bouton de fenêtre
BUTTON_SIZE_HEADER   = 27    # Largeur bouton header
BUTTON_SIZE_HEADER_H = 28    # Hauteur bouton header
