# -*- coding: utf-8 -*-
"""Gestionnaire de cycle de vie du processus local llama-server.exe."""

import atexit
import os
import subprocess
import sys
from typing import Optional, Tuple

from src.config.schema import APP_DIR, LOGGER


class LlamaServerManager:
    """Contrôle le démarrage, l'arrêt et la surveillance de llama-server."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.log_handle = None

    @property
    def pid(self) -> Optional[int]:
        """Retourne le PID du processus s'il est actif, sinon None."""
        if self.is_running() and self.process is not None:
            return self.process.pid
        return None

    def _path(self, value: str) -> str:
        expanded = os.path.expandvars(os.path.expanduser(str(value).strip().strip('"')))
        if not os.path.isabs(expanded):
            expanded = os.path.join(APP_DIR, expanded)
        return os.path.normpath(expanded)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, config: dict) -> Tuple[bool, str]:
        if self.is_running():
            return True, "Serveur déjà démarré"

        cfg = config.get("llama_server", {})
        exe = self._path(cfg.get("executable", "llama-server.exe"))
        model = self._path(cfg.get("model", ""))

        if not os.path.isfile(exe):
            return False, f"Exécutable introuvable : {exe}"
        if not os.path.isfile(model):
            return False, f"Modèle introuvable : {model}"

        command = [exe, "-m", model] + [str(x) for x in cfg.get("arguments", [])]
        try:
            log_path = os.path.join(APP_DIR, "llama-server.log")
            self.log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                command,
                cwd=os.path.dirname(exe),
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
            )
            return True, f"Démarrage en cours, PID {self.process.pid}"
        except (OSError, ValueError) as error:
            self.process = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:
                    pass
                self.log_handle = None
            return False, str(error)

    def stop(self) -> Tuple[bool, str]:
        if not self.is_running():
            self.process = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:
                    pass
                self.log_handle = None
            return True, "Serveur arrêté"

        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            return True, "Serveur arrêté"
        except OSError as error:
            return False, str(error)
        finally:
            self.process = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:
                    pass
                self.log_handle = None


_SERVER_MANAGER_INSTANCE: Optional[LlamaServerManager] = None


def get_server_manager() -> LlamaServerManager:
    """Retourne l'instance partagée du gestionnaire llama-server."""
    global _SERVER_MANAGER_INSTANCE
    if _SERVER_MANAGER_INSTANCE is None:
        _SERVER_MANAGER_INSTANCE = LlamaServerManager()
        atexit.register(_SERVER_MANAGER_INSTANCE.stop)
    return _SERVER_MANAGER_INSTANCE
