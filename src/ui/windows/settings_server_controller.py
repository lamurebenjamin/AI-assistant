"""Configuration et controle du processus llama-server local."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from src.ui.windows.settings_config import normalize_server_config


def browse_server_executable(self):
    path, _ = QFileDialog.getOpenFileName(self, "Sélectionner llama-server.exe", "", "Exécutable (*.exe);;Tous les fichiers (*)")
    if path: self.server_exe_input.setText(path)


def browse_server_model(self):
    path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le modèle GGUF", "", "Modèle GGUF (*.gguf);;Tous les fichiers (*)")
    if path: self.server_model_input.setText(path)


def collect_server_config(self):
    return normalize_server_config(
        self.server_autostart_check.isChecked(),
        self.server_exe_input.text(),
        self.server_model_input.text(),
        self.server_args_input.toPlainText().splitlines(),
    )


def start_local_server(self):
    runtime = dict(self.config); runtime['llama_server'] = self.collect_server_config()
    ok, message = self._server_manager.start(runtime)
    self.server_process_status.setText("PROCESSUS DÉMARRÉ" if ok else "ÉCHEC DU DÉMARRAGE")
    self.server_process_status.set_tone("success" if ok else "danger", weight=700)
    self.server_process_status.setToolTip(message)
    QTimer.singleShot(800, self.refresh_runtime_status)


def stop_local_server(self):
    ok, message = self._server_manager.stop()
    self.server_process_status.setText("PROCESSUS ARRÊTÉ" if ok else "ÉCHEC DE L'ARRÊT")
    self.server_process_status.set_tone("muted" if ok else "danger", weight=700)
    self.server_process_status.setToolTip(message)
    QTimer.singleShot(250, self.refresh_runtime_status)
