"""Effets de la fenetre des parametres."""
from src.ui.theme import apply_rounded_corners


def apply_effects(self):
    # Pas d'Acrylic dans Paramètres : cela garantit que toute la zone cliente
    # reste interactive de manière fiable sous Windows 10/11.
    hwnd = int(self.winId())
    apply_rounded_corners(hwnd)
    self.raise_()
    self.activateWindow()
