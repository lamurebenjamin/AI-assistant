"""Point d'entrée principal de l'Assistant IA (compatible avec les raccourcis existants)."""

import ctypes
import logging
import sys

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

from src.app.hotkey_managers import (
    MenuHotkeyManager,
    NumericHotkeyManager,
    VoiceHotkeyManager,
)
from src.config.manager import load_config, save_config
from src.config.schema import (
    APP_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    HTTP_TIMEOUT,
    LOG_FORMAT,
    LOGGER,
    STATUS_TIMEOUT,
)
from src.llm.server_manager import LlamaServerManager, get_server_manager
from src.ui.icons import (
    ICONS,
    ICONS_DARK,
    create_svg_icon,
    initialize_icons,
)
from src.ui.theme import (
    apply_acrylic_blur,
    apply_light_popup_theme,
    apply_rounded_corners,
)
from src.ui.tray import create_tray_icon
from src.ui.windows.assistant_window import AssistantWindow
from src.ui.windows.document_dialog import DocumentDialog
from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog
from src.ui.windows.settings_dialog import SettingsDialog

LLAMA_SERVER_MANAGER = get_server_manager()


def main() -> int:
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
    app.aboutToQuit.connect(LLAMA_SERVER_MANAGER.stop)

    if QSystemTrayIcon.isSystemTrayAvailable():
        # Conserver une référence empêche Python de détruire l'icône.
        app.tray_icon = create_tray_icon(app, assistant)
        assistant.start_server_online_notification(app.tray_icon)
    else:
        LOGGER.warning("Zone de notification Windows indisponible.")

    # Les trois familles de raccourcis sont pilotées depuis l'icône système.
    app.menu_hotkey_manager = MenuHotkeyManager(assistant)

    # Ctrl+0 à Ctrl+9 : suppression automatique du zoom Adobe Reader/Acrobat
    # lorsque ces applications sont au premier plan, sinon comportement normal
    # (les raccourcis Ctrl+1 à Ctrl+9 de l'assistant restent toujours actifs).
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


if __name__ == "__main__":
    raise SystemExit(main())
