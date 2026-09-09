# -*- coding: utf-8 -*-
"""Tokens de design centralisés pour l'application Assistant IA.

Ce module est la source de vérité unique pour toutes les valeurs
visuelles : couleurs, typographies, espacements et rayons.
Aucune valeur ne doit être hardcodée dans les fichiers UI —
toutes les références passent par ces constantes.
"""

# ── Neutrals / Texte ─────────────────────────────────────────────────────────
COLOR_TEXT_PRIMARY    = "#111111"   # Texte principal
COLOR_TEXT_SECONDARY  = "#4B5563"   # Sous-labels, secondaire
COLOR_TEXT_MUTED      = "#8A949F"   # Désactivé, placeholder
COLOR_TEXT_INVERSE    = "#FFFFFF"   # Texte sur fond sombre

# ── Backgrounds ──────────────────────────────────────────────────────────────
COLOR_BG_PAGE         = "#F8FAFC"   # Fond fenêtres opaques
COLOR_BG_SURFACE      = "#FFFFFF"   # Fond champs, cards
COLOR_BG_SUBTLE       = "#F1F5F9"   # Alternance, hover léger
COLOR_BG_ACRYLIC      = "rgba(255,255,255,34)"   # Panneau translucide
COLOR_BORDER_ACRYLIC  = "rgba(255,255,255,60)"   # Bordure panneau translucide

# ── Borders ──────────────────────────────────────────────────────────────────
COLOR_BORDER          = "#CBD7E4"   # Bordure standard
COLOR_BORDER_STRONG   = "#AAB8C7"   # Focus / hover
COLOR_BORDER_SUBTLE   = "#DDE6F0"   # Bordure très légère
COLOR_BORDER_INPUT    = "rgba(8,74,144,70)"  # Bordure champs de saisie

# ── Brand / Primary (bleu) ───────────────────────────────────────────────────
COLOR_PRIMARY         = "#2563B8"   # Bouton principal, sélection liste
COLOR_PRIMARY_HOVER   = "#1D4F96"   # Hover bouton principal
COLOR_PRIMARY_ACTIVE  = "#173F78"   # Pressed bouton principal
COLOR_PRIMARY_LIGHT   = "#DCEBFF"   # Fond bulle user / zone surlignée
COLOR_PRIMARY_BORDER  = "#B7D3F7"   # Bordure bulle user
COLOR_PRIMARY_SUBTLE  = "rgba(37,99,184,18)"  # Survol léger zone bleue

# ── Success / Vert ───────────────────────────────────────────────────────────
COLOR_SUCCESS         = "#397D58"   # TTS actif, points de pensée
COLOR_SUCCESS_LIGHT   = "#EFF9F2"   # Fond bulle assistant
COLOR_SUCCESS_BORDER  = "#C9E8D3"   # Bordure bulle assistant
COLOR_SUCCESS_TEXT    = "#183B28"   # Texte dans bulle assistant
COLOR_SUCCESS_STRONG  = "#16833B"   # Badge succès fort

# ── User bubble text ─────────────────────────────────────────────────────────
COLOR_USER_TEXT       = "#17324D"   # Texte dans bulle utilisateur

# ── Danger / Erreur ──────────────────────────────────────────────────────────
COLOR_DANGER          = "#C62828"   # Erreur, bouton destructeur
COLOR_DANGER_ALT      = "#D13438"   # Variante danger (suppression)
COLOR_WARNING         = "#C47F00"   # Avertissement

# ── Interactive overlays ─────────────────────────────────────────────────────
COLOR_HOVER_DARK      = "rgba(0,0,0,18)"     # Survol sur fond clair
COLOR_PRESS_DARK      = "rgba(0,0,0,35)"     # Press sur fond clair
COLOR_HOVER_LIGHT     = "rgba(255,255,255,34)"  # Survol sur fond sombre
COLOR_PRESS_LIGHT     = "rgba(255,255,255,60)"  # Press sur fond sombre

# ── Scrollbar ────────────────────────────────────────────────────────────────
COLOR_SCROLLBAR_TRACK = "rgba(0,0,0,14)"
COLOR_SCROLLBAR_THUMB = "rgba(30,30,30,85)"
COLOR_SCROLLBAR_HOVER = "rgba(30,30,30,135)"

# ── Palette étendue (dialogs, listes) ────────────────────────────────────────
COLOR_GRAY_100        = "#EEF3F8"
COLOR_GRAY_200        = "#E9EEF4"
COLOR_GRAY_300        = "#E6EDF4"
COLOR_GRAY_500        = "#747B84"
COLOR_GRAY_600        = "#5E6670"
COLOR_GRAY_700        = "#52677C"

# ── Audio bars ───────────────────────────────────────────────────────────────
COLOR_AUDIO_ACTIVE    = "#0A68D8"   # Barre audio active (proche de PRIMARY)
COLOR_AUDIO_IDLE      = "#8993A0"   # Barre audio inactive (proche de TEXT_MUTED)

# ── Border-radius scale ───────────────────────────────────────────────────────
RADIUS_XS   = "3px"    # Tags, petits badges
RADIUS_SM   = "4px"    # Champs, items de liste, scrollbar thumb
RADIUS_MD   = "6px"    # Boutons standard, scrollbar track
RADIUS_LG   = "8px"    # Boutons CTA, onglets, panneaux internes
RADIUS_XL   = "14px"   # Bulles de chat, boutons icônes, zoom loupe
RADIUS_2XL  = "16px"   # Panneaux principaux (acrylic), header badge

# ── Typographies ─────────────────────────────────────────────────────────────
FONT_DISPLAY = "'Aptos Display','Segoe UI Variable Display','Segoe UI',Arial"
FONT_TEXT    = "'Aptos','Segoe UI Variable Text','Segoe UI',Arial"
FONT_MENU    = "'Segoe UI Variable','Segoe UI',Arial"

# ── Tailles de police ─────────────────────────────────────────────────────────
SIZE_XS  = "10px"   # Métadonnées, annotations
SIZE_SM  = "11px"   # Labels compacts
SIZE_MD  = "12px"   # Corps de texte, bulles, menus
SIZE_LG  = "13px"   # UI standard (boutons, labels, champs)
SIZE_XL  = "15px"   # Titres de section importants

# ── Espacements (px) ─────────────────────────────────────────────────────────
SPACING_XS  = 3
SPACING_SM  = 6
SPACING_MD  = 9
SPACING_LG  = 12
SPACING_XL  = 16

# ── Dimensions fixes communes ─────────────────────────────────────────────────
HEADER_HEIGHT       = 36    # Hauteur de la barre de titre
ICON_SIZE_HEADER    = 18    # Icône logo dans le header
ICON_SIZE_BUTTON    = 19    # Icône dans bouton de fenêtre
BUTTON_SIZE_HEADER  = 27    # Largeur bouton header
BUTTON_SIZE_HEADER_H = 28   # Hauteur bouton header
