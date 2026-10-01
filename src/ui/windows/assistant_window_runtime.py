"""Surveillance des ressources et fenetre de diagnostic."""

import os

from src.monitoring.runtime_info import RuntimeInfoThread
from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog


def show_runtime_information(self, *, server_manager):
    """Ouvre une fenêtre et actualise les ressources de l'application."""
    if self.runtime_info_dialog is None:
        self.runtime_info_dialog = RuntimeInfoDialog(self)

    self.runtime_info_dialog.set_information("Collecte des informations...")
    self.runtime_info_dialog.show()
    self.runtime_info_dialog.raise_()
    self.runtime_info_dialog.activateWindow()

    if self.runtime_info_thread is not None and self.runtime_info_thread.isRunning():
        return

    # L'application comprend l'interface Python et le serveur llama.cpp lancé ici.
    process_ids = {os.getpid()}
    if server_manager.is_running():
        process_ids.add(server_manager.process.pid)

    self.runtime_info_thread = RuntimeInfoThread(
        self.config.get("api_url", ""),
        process_ids,
        self,
        server_manager.auth_token,
    )
    self.runtime_info_thread.info_ready.connect(self._display_runtime_information)
    self.runtime_info_thread.finished.connect(self._on_runtime_info_finished)
    self.runtime_info_thread.start()


def _display_runtime_information(self, information):
    if self.runtime_info_dialog is not None:
        self.runtime_info_dialog.set_information(information)


def _on_runtime_info_finished(self):
    thread = self.sender()
    if thread is self.runtime_info_thread:
        self.runtime_info_thread = None
    if thread is not None:
        thread.deleteLater()
