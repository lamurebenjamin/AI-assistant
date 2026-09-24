"""Tests d'harmonisation des icônes et boutons.

Règle : TOUTES les icônes de l'application doivent avoir un chemin SVG
déclaré dans ``src.ui.icons._SVG``.  Ce test garantit qu'aucune icône
ne peut être rendue sans passer par la source unique.

Exécution
---------
    python -m pytest tests/test_icon_consistency.py -v
    # ou
    python -m unittest tests.test_icon_consistency -v
"""

import unittest
from typing import ClassVar


class TestIconRegistry(unittest.TestCase):
    """Vérifie que _SVG contient toutes les icônes requises."""

    # Icônes utilisées par AnimatedComposerButton
    COMPOSER_KINDS: ClassVar[set[str]] = {"add", "mic", "send", "stop", "close"}

    # Icônes utilisées par AnimatedHeaderButton dans assistant_window.py
    HEADER_ICONS: ClassVar[set[str]] = {"speak", "speak_filled", "copy", "close"}

    # Icônes communes (boutons settings, etc.)
    COMMON_ICONS: ClassVar[set[str]] = {
        "settings", "up", "down", "delete", "save", "cancel", "regenerate", "check"
    }

    def _get_svg_registry(self):
        """Importe _SVG sans créer de QApplication."""
        import ast
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "src" / "ui" / "icons.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_SVG":
                        return {k.value: True for k in node.value.keys}
        return {}

    def test_composer_kinds_in_svg(self):
        """Tous les kinds de AnimatedComposerButton ont un SVG déclaré."""
        registry = self._get_svg_registry()
        missing = self.COMPOSER_KINDS - set(registry.keys())
        self.assertFalse(
            missing,
            f"Icônes manquantes dans _SVG pour AnimatedComposerButton : {missing}\n"
            "Ajouter le chemin SVG dans src/ui/icons.py -> _SVG."
        )

    def test_header_icons_in_svg(self):
        """Toutes les icônes de AnimatedHeaderButton ont un SVG déclaré."""
        registry = self._get_svg_registry()
        missing = self.HEADER_ICONS - set(registry.keys())
        self.assertFalse(
            missing,
            f"Icônes manquantes dans _SVG pour AnimatedHeaderButton : {missing}\n"
            "Ajouter le chemin SVG dans src/ui/icons.py -> _SVG."
        )

    def test_common_icons_in_svg(self):
        """Toutes les icônes communes ont un SVG déclaré."""
        registry = self._get_svg_registry()
        missing = self.COMMON_ICONS - set(registry.keys())
        self.assertFalse(
            missing,
            f"Icônes communes manquantes dans _SVG : {missing}"
        )

    def test_no_empty_svg_paths(self):
        """Aucun chemin SVG ne doit être vide."""
        import ast
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "src" / "ui" / "icons.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        svg_dict = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_SVG":
                        for k, v in zip(node.value.keys, node.value.values):
                            svg_dict[k.value] = v.value if hasattr(v, 'value') else ""
        empty = [k for k, v in svg_dict.items() if not v or not v.strip()]
        self.assertFalse(empty, f"Chemins SVG vides dans _SVG : {empty}")

    def test_dark_stroke_values_in_valid_range(self):
        """Toutes les épaisseurs dans _DARK_STROKE sont entre 0.5 et 3.0."""
        import ast
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "src" / "ui" / "icons.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_DARK_STROKE":
                        for k, v in zip(node.value.keys, node.value.values):
                            key = k.value
                            val = v.value
                            self.assertGreaterEqual(
                                val, 0.5,
                                f"_DARK_STROKE[{key!r}] trop faible : {val}"
                            )
                            self.assertLessEqual(
                                val, 3.0,
                                f"_DARK_STROKE[{key!r}] trop élevé : {val}"
                            )


class TestButtonHarmonization(unittest.TestCase):
    """Règles d'harmonisation structurelle entre les classes de boutons."""

    @staticmethod
    def _read_buttons():
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "src" / "ui" / "widgets" / "animated_buttons.py"
        return src.read_text(encoding="utf-8")

    @staticmethod
    def _split_sections(code: str):
        composer_idx = code.index("class AnimatedComposerButton")
        header_idx = code.index("class AnimatedHeaderButton")
        return code[composer_idx:header_idx], code[header_idx:]

    def test_both_buttons_same_size_constants(self):
        """AnimatedComposerButton et AnimatedHeaderButton référencent BUTTON_SIZE_HEADER."""
        code = self._read_buttons()
        composer, header = self._split_sections(code)
        self.assertIn("BUTTON_SIZE_HEADER", composer,
                      "AnimatedComposerButton doit utiliser t.BUTTON_SIZE_HEADER")
        self.assertIn("BUTTON_SIZE_HEADER", header,
                      "AnimatedHeaderButton doit utiliser t.BUTTON_SIZE_HEADER")

    def test_both_buttons_use_tooltip_filter(self):
        """Les deux classes installent ToolTipFilter pour harmoniser les tooltips."""
        code = self._read_buttons()
        self.assertIn("_ToolTipFilter", code,
                      "ToolTipFilter doit être utilisé dans animated_buttons.py")

    def test_composer_uses_icons_dark(self):
        """AnimatedComposerButton doit lire ses icônes depuis ICONS_DARK."""
        code = self._read_buttons()
        composer, _ = self._split_sections(code)
        self.assertIn("ICONS_DARK", composer,
                      "AnimatedComposerButton doit utiliser ICONS_DARK comme source d'icônes")

    def test_no_hardcoded_icon_drawing_in_composer(self):
        """AnimatedComposerButton ne doit pas avoir de constante ICON_EXTENT hardcodée."""
        code = self._read_buttons()
        composer, _ = self._split_sections(code)
        self.assertNotIn("ICON_EXTENT", composer,
                         "ICON_EXTENT ne doit plus exister dans AnimatedComposerButton — "
                         "utiliser ICONS_DARK a la place")


if __name__ == "__main__":
    unittest.main()
