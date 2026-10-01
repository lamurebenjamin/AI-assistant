"""Fenetre des parametres : facade Qt et orchestration des composants."""
import copy
import ctypes
import sys

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QDialog

from src.config.schema import DEFAULT_CONFIG
from src.llm.server_manager import get_server_manager
from src.ui.windows import settings_actions_controller as _settings_actions_controller
from src.ui.windows import (
    settings_appearance_controller as _settings_appearance_controller,
)
from src.ui.windows import settings_audio_controller as _settings_audio_controller
from src.ui.windows import settings_config_controller as _settings_config_controller
from src.ui.windows import settings_dialog_view as _settings_dialog_view
from src.ui.windows import settings_runtime_controller as _settings_runtime_controller
from src.ui.windows import settings_server_controller as _settings_server_controller
from src.ui.windows import settings_window_behavior as _settings_window_behavior
from src.ui.windows.settings_config import copy_server_config

LLAMA_SERVER_MANAGER = get_server_manager()

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._server_manager = LLAMA_SERVER_MANAGER
        self.temp_actions = [a.copy() for a in config['actions']]
        self.temp_api_url = config['api_url']
        self.temp_voice_config = copy.deepcopy(config.get('voice_input', DEFAULT_CONFIG['voice_input']))
        self.temp_tts_config = copy.deepcopy(config.get('text_to_speech', DEFAULT_CONFIG['text_to_speech']))
        self.mic_test_thread = None
        self.temp_server_config = copy_server_config(config.get("llama_server"))
        self.is_updating_ui = False
        self.drag_position = None
        self.status_thread = None
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(5000)
        self.status_timer.timeout.connect(self.refresh_runtime_status)
        self.status_debounce_timer = QTimer(self)
        self.status_debounce_timer.setSingleShot(True)
        self.status_debounce_timer.setInterval(500)
        self.status_debounce_timer.timeout.connect(self.check_server_status)
        self.nvidia_thread = None
        self.initUI()

    def initUI(self):
        panel_layout, content_layout, llm_layout, voice_layout, shortcuts_layout = _settings_dialog_view.build_shell(self)
        _settings_dialog_view.build_llm_section(self, llm_layout)
        _settings_dialog_view.build_voice_section(self, voice_layout)
        _settings_dialog_view.build_shortcuts_section(self, shortcuts_layout)
        _settings_dialog_view.build_footer(self, panel_layout, content_layout)

    def eventFilter(self, watched, event):
        # Le déplacement est limité à l'en-tête. Sous Windows, le déplacement
        # natif est utilisé afin d'éviter les traces de repeinture et les widgets
        # dupliqués visuellement pendant le glissement.
        if watched is self.header:
            if event.type() == QEvent.MouseButtonDblClick:
                event.accept()
                return True

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if sys.platform == 'win32':
                    try:
                        WM_NCLBUTTONDOWN = 0x00A1
                        HTCAPTION = 0x0002
                        hwnd = int(self.winId())
                        ctypes.windll.user32.ReleaseCapture()
                        ctypes.windll.user32.SendMessageW(
                            hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0
                        )
                    except (AttributeError, OSError, TypeError, ValueError):
                        self.drag_position = (
                            event.globalPos() - self.frameGeometry().topLeft()
                        )
                else:
                    self.drag_position = (
                        event.globalPos() - self.frameGeometry().topLeft()
                    )
                event.accept()
                return True

            # Repli uniquement pour les plateformes sans déplacement natif.
            if (sys.platform != 'win32' and
                    event.type() == QEvent.MouseMove and
                    self.drag_position is not None and
                    event.buttons() & Qt.LeftButton):
                self.move(event.globalPos() - self.drag_position)
                event.accept()
                return True

            if event.type() == QEvent.MouseButtonRelease:
                self.drag_position = None
                self.repaint()
                self.panel.repaint()
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        # Une mise à jour différée évite les restes visuels après déplacement.
        QTimer.singleShot(0, self.update)

    def showEvent(self, event):
        super().showEvent(event)
        self.drag_position = None
        self.panel.setEnabled(True)
        self.panel.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Centre toujours la fenêtre sur l'écran actif pour éviter les affichages
        # partiels ou hors écran, notamment avec plusieurs moniteurs.
        parent = self.parentWidget()
        if parent is not None:
            screen = QApplication.screenAt(parent.frameGeometry().center())
        else:
            screen = QApplication.screenAt(QCursor.pos())
        screen = screen or QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(
            available.x() + (available.width() - self.width()) // 2,
            available.y() + (available.height() - self.height()) // 2
        )

        QTimer.singleShot(0, self.apply_effects)
        QTimer.singleShot(100, self.refresh_runtime_status)
        self.status_timer.start()

    def shutdown_background_threads(self):
        return _settings_runtime_controller.shutdown_background_threads(self)

    def done(self, result):
        # done() est appelé par Fermer, Annuler, Sauvegarder et reject().
        self.shutdown_background_threads()
        super().done(result)

    def closeEvent(self, event):
        self.shutdown_background_threads()
        super().closeEvent(event)

    def refresh_runtime_status(self):
        return _settings_runtime_controller.refresh_runtime_status(self)

    def check_nvidia_status(self):
        return _settings_runtime_controller.check_nvidia_status(self)

    def on_nvidia_thread_finished(self):
        return _settings_runtime_controller.on_nvidia_thread_finished(self)

    def update_nvidia_status(self, available, pstate, detail):
        return _settings_runtime_controller.update_nvidia_status(self, available, pstate, detail)

    def schedule_server_status_check(self):
        # Redémarrer un timer unique évite des contrôles réseau obsolètes à chaque frappe.
        return _settings_runtime_controller.schedule_server_status_check(self)

    def check_server_status(self):
        return _settings_runtime_controller.check_server_status(self)

    def on_status_thread_finished(self):
        return _settings_runtime_controller.on_status_thread_finished(self)

    def update_server_status(self, online, detail, model_name):
        return _settings_runtime_controller.update_server_status(self, online, detail, model_name)

    def apply_effects(self):
        # Pas d'Acrylic dans Paramètres : cela garantit que toute la zone cliente
        # reste interactive de manière fiable sous Windows 10/11.
        return _settings_window_behavior.apply_effects(self)

    def populate_list(self):
        return _settings_actions_controller.populate_list(self)

    def on_action_selected(self, row):
        return _settings_actions_controller.on_action_selected(self, row)

    def update_action_field(self):
        return _settings_actions_controller.update_action_field(self)

    def add_action(self):
        return _settings_actions_controller.add_action(self)

    def del_action(self):
        return _settings_actions_controller.del_action(self)

    def move_action(self, direction):
        return _settings_actions_controller.move_action(self, direction)

    def browse_server_executable(self):
        return _settings_server_controller.browse_server_executable(self)

    def browse_server_model(self):
        return _settings_server_controller.browse_server_model(self)

    def collect_server_config(self):
        return _settings_server_controller.collect_server_config(self)

    def start_local_server(self):
        return _settings_server_controller.start_local_server(self)

    def stop_local_server(self):
        return _settings_server_controller.stop_local_server(self)

    def refresh_audio_devices(self):
        return _settings_audio_controller.refresh_audio_devices(self)

    def toggle_microphone_test(self):
        return _settings_audio_controller.toggle_microphone_test(self)

    def _on_theme_preview_changed(self, _index=None):
        return _settings_appearance_controller._on_theme_preview_changed(self, _index)

    def refresh_theme(self) -> None:
        return _settings_appearance_controller.refresh_theme(self)

    def _refresh_ctrl9_preview(self, val=None):
        return _settings_appearance_controller._refresh_ctrl9_preview(self, val)

    def save(self):
        return _settings_config_controller.save(self)
