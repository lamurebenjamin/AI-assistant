"""Tests pour la boîte de dialogue des paramètres et l'isolation des onglets.

Vérifie notamment qu'aucun onglet ne se superpose lors de la navigation
et qu'une seule page est visible à la fois dans le QStackedWidget.
"""

import unittest
from copy import deepcopy

from PySide6.QtWidgets import QApplication, QStackedWidget

from src.config.schema import DEFAULT_CONFIG
from src.ui.icons import initialize_icons
from src.ui.windows.settings_config import (
    copy_server_config,
    normalize_api_url,
    normalize_server_config,
)
from src.ui.windows.settings_dialog import SettingsDialog
from src.ui.windows.settings_tabs import AppearanceTab, Ctrl9Tab


class SettingsDialogTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        initialize_icons()

    def setUp(self):
        self.dialog = SettingsDialog(deepcopy(DEFAULT_CONFIG))

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()

    def test_settings_stack_is_qstackedwidget(self):
        """Vérifie que la pile de pages utilise un QStackedWidget natif sans superposition."""
        self.assertIsInstance(self.dialog.settings_stack, QStackedWidget)

    def test_tab_isolation_no_superposition(self):
        """Vérifie qu'à chaque changement d'onglet, exactement 1 page est visible."""
        self.dialog.show()
        pivot = self.dialog.settings_tabs
        stack = self.dialog.settings_stack

        tab_keys = ["llm", "voice", "shortcuts", "ctrl9", "appearance"]
        for key in tab_keys:
            with self.subTest(tab=key):
                pivot.widget(key).click()
                self.app.processEvents()

                # Une seule page doit être visible (non masquée)
                visible_pages = [
                    i for i in range(stack.count())
                    if not stack.widget(i).isHidden()
                ]
                self.assertEqual(
                    len(visible_pages),
                    1,
                    f"Superposition détectée sur l'onglet '{key}': pages visibles = {visible_pages}"
                )


class SettingsConfigTests(unittest.TestCase):
    def test_normalize_server_config_strips_arguments_and_values(self):
        result = normalize_server_config(
            1,
            "  llama-server.exe ",
            " model.gguf ",
            [" --port ", "", 8080, "  "],
        )
        self.assertEqual(
            result,
            {
                "auto_start": True,
                "executable": "llama-server.exe",
                "model": "model.gguf",
                "arguments": ["--port", "8080"],
            },
        )

    def test_copy_server_config_handles_missing_values(self):
        self.assertEqual(
            copy_server_config(None),
            {
                "auto_start": True,
                "executable": "llama-server.exe",
                "model": "",
                "arguments": [],
            },
        )

    def test_normalize_api_url_falls_back_for_invalid_value(self):
        self.assertEqual(normalize_api_url("ftp://invalid"), DEFAULT_CONFIG["api_url"])
        self.assertEqual(
            normalize_api_url(" https://localhost:8080/v1/chat/completions "),
            "https://localhost:8080/v1/chat/completions",
        )


class SettingsTabComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        initialize_icons()

    def test_appearance_tab_owns_theme_selector(self):
        changes = []
        tab = AppearanceTab({"theme": "light"}, changes.append)
        self.assertEqual(tab.theme_combo.currentIndex(), 1)
        tab.theme_combo.setCurrentIndex(0)
        self.app.processEvents()
        self.assertEqual(changes, [0])

    def test_ctrl9_tab_owns_independent_controls(self):
        previews = []
        tab = Ctrl9Tab({"ctrl9": {"width": 720, "max_height": 800, "font_size": 16}}, previews.append)
        self.assertEqual(tab.width_spin.value(), 720)
        self.assertEqual(tab.max_height_spin.value(), 800)
        self.assertEqual(tab.font_size_spin.value(), 16)
        tab.font_btn_plus.click()
        self.assertEqual(tab.font_size_spin.value(), 17)


if __name__ == "__main__":
    unittest.main()
