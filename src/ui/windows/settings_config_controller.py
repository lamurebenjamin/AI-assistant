"""Collecte et sauvegarde de la configuration des parametres."""
import copy

from PySide6.QtWidgets import QApplication

from src.config.manager import save_config
from src.ui.theme import apply_app_theme
from src.ui.windows.settings_config import normalize_api_url


def save(self):
    selected = self.voice_device_combo.currentData()
    self.config['voice_input'] = copy.deepcopy(self.temp_voice_config)
    self.config['voice_input']['enabled'] = self.voice_enabled_check.isChecked()
    self.config['voice_input']['input_device'] = selected.get("index") if isinstance(selected, dict) else None
    self.config['voice_input']['input_device_name'] = selected.get("name", "") if isinstance(selected, dict) else ""
    self.config['text_to_speech'] = copy.deepcopy(self.temp_tts_config)
    self.config['text_to_speech']['automatic_reading'] = self.automatic_reading_check.isChecked()
    self.config["api_url"] = normalize_api_url(self.api_input.text())
    self.config['llama_server'] = self.collect_server_config()
    self.config['actions'] = self.temp_actions
    if hasattr(self, 'theme_combo'):
        chosen_theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
        self.config['theme'] = chosen_theme
        app = QApplication.instance()
        if app:
            apply_app_theme(app, chosen_theme)
    if hasattr(self, 'ctrl9_width_spin'):
        self.config['ctrl9'] = {
            'width': self.ctrl9_width_spin.value(),
            'max_height': self.ctrl9_max_height_spin.value(),
            'font_size': self.ctrl9_font_size_spin.value(),
        }
    save_config(self.config)
    self.accept()
