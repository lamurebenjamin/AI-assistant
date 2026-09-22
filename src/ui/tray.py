"""Gestion de l'icône dans la zone de notification Windows (systray)."""

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.config.schema import APP_DIR
from src.ui.icons import get_app_icon
from src.ui.stylesheet import qss_menu


def create_tray_icon(app, assistant):
    """Crée l'icône près de l'horloge Windows.

    Un clic gauche sur l'icône n'ouvre aucune fenêtre.
    Le clic droit propose Afficher, Paramètres et Quitter.
    """
    tray_icon = QSystemTrayIcon(app)

    # Icône multi-résolution (inclut 40x40 pour showMessage, 16/24/32 pour le tray, etc.)
    icon = get_app_icon(APP_DIR)

    app.setWindowIcon(icon)
    tray_icon.setIcon(icon)
    tray_icon.setToolTip("Assistant IA")

    tray_menu = QMenu()
    tray_menu.setObjectName("TrayLightMenu")
    tray_menu.setAttribute(Qt.WA_TranslucentBackground, False)
    tray_menu.setAutoFillBackground(True)
    tray_menu.setStyleSheet(qss_menu("TrayLightMenu", padding=6))
    settings_action = QAction("Paramètres", tray_menu)
    hotkeys_enabled = bool(assistant.config.get("hotkeys_enabled", True))
    hotkeys_action = QAction(
        "Désactiver les raccourcis" if hotkeys_enabled
        else "Activer les raccourcis",
        tray_menu,
    )
    automatic_reading_enabled = bool(
        assistant.config.get("text_to_speech", {}).get("automatic_reading", False)
    )
    automatic_reading_action = QAction(
        "Désactiver la lecture à voix haute" if automatic_reading_enabled
        else "Activer la lecture à voix haute",
        tray_menu,
    )
    quit_action = QAction("Quitter", tray_menu)

    settings_action.triggered.connect(assistant.open_settings)
    hotkeys_action.triggered.connect(lambda: assistant.toggle_hotkeys())
    automatic_reading_action.triggered.connect(assistant.toggle_automatic_reading)
    app.hotkeys_action = hotkeys_action
    app.automatic_reading_action = automatic_reading_action
    quit_action.triggered.connect(assistant.quit_application)

    tray_menu.addAction(settings_action)
    tray_menu.addAction(hotkeys_action)
    tray_menu.addAction(automatic_reading_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)
    tray_icon.setContextMenu(tray_menu)

    def handle_tray_activation(reason):
        # Trigger correspond au clic gauche simple dans QSystemTrayIcon.
        if reason == QSystemTrayIcon.Trigger:
            assistant.show_runtime_information()

    tray_icon.activated.connect(handle_tray_activation)
    tray_icon.show()
    return tray_icon
