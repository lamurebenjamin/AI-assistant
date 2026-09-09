"""Gestion de l'icône dans la zone de notification Windows (systray)."""

import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon

from src.config.schema import APP_DIR
from src.ui.icons import create_svg_icon


def create_tray_icon(app, assistant):
    """Crée l'icône près de l'horloge Windows.

    Un clic gauche sur l'icône n'ouvre aucune fenêtre.
    Le clic droit propose Afficher, Paramètres et Quitter.
    """
    tray_icon = QSystemTrayIcon(app)

    # Logo fourni avec l'application, inspiré de la pièce jointe.
    # Le chemin reste valide même si l'application est lancée depuis un autre dossier.
    icon_path = os.path.join(
        APP_DIR,
        "assistant_icon.webp"
    )
    icon = QIcon(icon_path)
    if icon.isNull():
        # Icône de secours si le fichier visuel est absent.
        fallback_svg = (
            '<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 '
            'C7.5 12.8 11.2 16.5 12 22.5 '
            'C12.8 16.5 16.5 12.8 22.5 12 '
            'C16.5 11.2 12.8 7.5 12 1.5z"/>'
        )
        icon = create_svg_icon(fallback_svg, "#FFFFFF")
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)

    app.setWindowIcon(icon)
    tray_icon.setIcon(icon)
    tray_icon.setToolTip("Assistant IA")

    tray_menu = QMenu()
    tray_menu.setObjectName("TrayLightMenu")
    tray_menu.setAttribute(Qt.WA_TranslucentBackground, False)
    tray_menu.setAutoFillBackground(True)
    tray_menu.setStyleSheet("""
        QMenu#TrayLightMenu {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 6px;
            font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
            font-size: 13px;
        }
        QMenu#TrayLightMenu::item {
            background: transparent;
            color: #111111;
            padding: 7px 24px 7px 12px;
            margin: 1px;
            border-radius: 5px;
        }
        QMenu#TrayLightMenu::item:selected {
            background-color: #DCEBFF;
            color: #111111;
        }
        QMenu#TrayLightMenu::separator {
            height: 1px;
            background-color: #D7E0EA;
            margin: 5px 8px;
        }
    """)
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
