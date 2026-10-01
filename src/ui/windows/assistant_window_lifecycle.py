"""Arret de l application et edition des parametres."""

import keyboard
from PySide6.QtWidgets import QApplication

from src.config.manager import load_config
from src.config.schema import LOGGER
from src.ui.windows.settings_dialog import SettingsDialog


def quit_application(self, *, server_manager):
    self.shutdown_background_threads()
    server_manager.stop()
    app = QApplication.instance()

    # Arreter chaque gestionnaire avant le nettoyage global. Sinon,
    # aboutToQuit peut tenter de supprimer une seconde fois un raccourci
    # deja retire et provoquer ValueError: list.remove(x): x not in list.
    for attribute in (
        "menu_hotkey_manager",
        "voice_hotkey_manager",
        "numeric_hotkey_manager",
    ):
        manager = getattr(app, attribute, None)
        if manager is not None:
            manager.stop()

    # Nettoyage de securite pour d'eventuels raccourcis residuels.
    keyboard.unhook_all_hotkeys()
    app.quit()


def shutdown_background_threads(self):
    """Arrête et attend tous les threads avant la destruction de la fenêtre."""
    if getattr(self, "_shutdown_started", False):
        return
    self._shutdown_started = True

    for timer_name in (
        "loading_timer",
        "stream_render_timer",
        "startup_status_timer",
    ):
        timer = getattr(self, timer_name, None)
        if timer is not None:
            timer.stop()

    threads = (
        ("llama", self.thread, "stop"),
        ("document", self.document_thread, "stop"),
        ("audio", self.audio_thread, "stop_recording"),
        ("tts", self.tts_thread, "stop"),
        ("runtime-info", self.runtime_info_thread, None),
        ("startup-status", getattr(self, "startup_status_thread", None), None),
        ("kokoro-warmup", self.kokoro_warmup_thread, None),
    )

    self.stop_speech()
    self.recording_indicator.hide()

    for name, thread, stop_method in threads:
        if thread is None or not thread.isRunning():
            continue
        if stop_method is not None:
            stop = getattr(thread, stop_method, None)
            if stop is not None:
                stop()
        else:
            thread.requestInterruption()
        if not thread.wait(10000):
            LOGGER.warning(
                "Le thread %s n'a pas terminé avant la fermeture de l'application",
                name,
            )

    self.thread = None
    self.document_thread = None
    self.audio_thread = None
    self.tts_thread = None
    self.runtime_info_thread = None
    self.startup_status_thread = None


def open_settings(self):
    self.cancel_voice_operation()
    manager = getattr(QApplication.instance(), "voice_hotkey_manager", None)
    if manager is not None: manager.set_enabled(False)
    dialog = SettingsDialog(self.config, self)
    if dialog.exec():
        self.config = load_config()
        self.set_automatic_reading_enabled(
            self._automatic_tts_enabled(), persist=False
        )
        if self.document_dialog is not None:
            self.document_dialog.apply_config(self.config.get("ctrl9", {}))
        self.label.setText("Paramètres mis à jour.")
        self.show_window()
    if manager is not None:
        manager.set_enabled(
            bool(self.config.get("hotkeys_enabled", True))
            and bool(self.config.get("voice_input", {}).get("enabled", True))
        )
