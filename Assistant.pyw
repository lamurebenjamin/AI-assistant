"""Point d'entrée de compatibilité ascendante de l'Assistant IA.

Ce module délègue l'exécution à `src.app.application.run()` tout en réexportant
les classes et fonctions historiques pour assurer une compatibilité totale avec
les raccourcis Windows existants (Assistant IA.lnk) et les scripts dépendants.
"""

from src.app.application import run
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
    """Exécute l'application via le gestionnaire de cycle de vie."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
