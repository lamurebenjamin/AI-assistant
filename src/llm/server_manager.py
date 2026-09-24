"""Gestionnaire de cycle de vie du processus local llama-server.exe."""

import atexit
import os
import secrets
import subprocess
import sys

from src.config.schema import APP_DIR


class LlamaServerManager:
    """Contrôle le cycle de vie de ``llama-server.exe``.

    ``start`` et ``stop`` retournent toujours ``(succès, message)`` :
    l'échec de validation des chemins ou de création du processus est explicite
    dans le message, sans lever d'exception applicative. ``stop`` termine le
    processus, puis force son arrêt après les délais prévus.
    """

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.auth_token: str | None = None

    @property
    def pid(self) -> int | None:
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

    def start(self, config: dict) -> tuple[bool, str]:
        if self.is_running():
            return True, "Serveur déjà démarré"

        cfg = config.get("llama_server", {})
        exe = self._path(cfg.get("executable", "llama-server.exe"))
        model = self._path(cfg.get("model", ""))

        if not os.path.isfile(exe):
            return False, f"Exécutable introuvable : {exe}"
        if not os.path.isfile(model):
            return False, f"Modèle introuvable : {model}"

        arguments = [str(x) for x in cfg.get("arguments", [])]
        filtered_arguments = []
        index = 0
        while index < len(arguments):
            if arguments[index] in {"--api-key", "--api-key-file"}:
                index += 2
                continue
            filtered_arguments.append(arguments[index])
            index += 1
        self.auth_token = secrets.token_urlsafe(32)
        command = [exe, "-m", model, *filtered_arguments, "--api-key", self.auth_token]
        try:
            log_path = os.path.join(APP_DIR, "llama-server.log")
            # Le handle doit rester ouvert pendant toute la durée du processus.
            self.log_handle = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
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
            self.auth_token = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:  # noqa: BLE001,S110
                    pass
                self.log_handle = None
            return False, str(error)

    def stop(self) -> tuple[bool, str]:
        if not self.is_running():
            self.process = None
            self.auth_token = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:  # noqa: BLE001,S110
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
            self.auth_token = None
            if self.log_handle:
                try:
                    self.log_handle.close()
                except Exception:  # noqa: BLE001,S110
                    pass
                self.log_handle = None


_SERVER_MANAGER_INSTANCE: LlamaServerManager | None = None


def get_server_manager() -> LlamaServerManager:
    """Retourne l'instance partagée du gestionnaire llama-server."""
    global _SERVER_MANAGER_INSTANCE
    if _SERVER_MANAGER_INSTANCE is None:
        _SERVER_MANAGER_INSTANCE = LlamaServerManager()
        atexit.register(_SERVER_MANAGER_INSTANCE.stop)
    return _SERVER_MANAGER_INSTANCE
