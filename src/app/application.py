"""Cycle de vie et orchestration globale de l'application Assistant IA."""

import ctypes
import logging
import sys

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

from src.app.hotkey_managers import (
    MenuHotkeyManager,
    NumericHotkeyManager,
    VoiceHotkeyManager,
)
from src.config.schema import LOG_FORMAT, LOGGER
from src.llm.server_manager import get_server_manager
from src.ui.icons import initialize_icons
from src.ui.theme import apply_light_popup_theme
from src.ui.tray import create_tray_icon
from src.ui.windows.assistant_window import AssistantWindow


def run() -> int:
    """Initialise l'application et retourne son code de sortie."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Assistant.IA"
            )
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    apply_light_popup_theme(app)
    app.setApplicationName("Assistant IA")
    app.setApplicationDisplayName("Assistant IA")
    app.setQuitOnLastWindowClosed(False)

    initialize_icons()
    assistant = AssistantWindow()
    server_manager = get_server_manager()
    app.aboutToQuit.connect(server_manager.stop)

    if QSystemTrayIcon.isSystemTrayAvailable():
        app.tray_icon = create_tray_icon(app, assistant)
        assistant.start_server_online_notification(app.tray_icon)
    else:
        LOGGER.warning("Zone de notification Windows indisponible.")

    app.menu_hotkey_manager = MenuHotkeyManager(assistant)
    app.numeric_hotkey_manager = NumericHotkeyManager(assistant, app)
    app.voice_hotkey_manager = VoiceHotkeyManager(assistant)
    assistant.set_hotkeys_enabled(
        bool(assistant.config.get("hotkeys_enabled", True)), persist=False
    )
    app.aboutToQuit.connect(app.menu_hotkey_manager.stop)
    app.aboutToQuit.connect(app.voice_hotkey_manager.stop)
    app.aboutToQuit.connect(app.numeric_hotkey_manager.stop)

    LOGGER.info("Assistant prêt.")
    LOGGER.info(
        "Sélectionnez du texte et appuyez sur Ctrl+. (menu) ou Ctrl+1 à Ctrl+9 (direct)."
    )

    return app.exec_()
