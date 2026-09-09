# -*- coding: utf-8 -*-
"""Thread de surveillance de l'état HTTP et du modèle actif de llama-server."""

import re
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from src.config.schema import STATUS_TIMEOUT


class ServerStatusThread(QThread):
    status_checked = pyqtSignal(bool, str, str)

    def __init__(self, api_url: str, parent=None):
        super().__init__(parent)
        self.api_url = api_url.strip()

    def run(self):
        try:
            match = re.match(r"^(https?://[^/]+)", self.api_url)
            if not match:
                self.status_checked.emit(False, "URL invalide", "")
                return

            base_url = match.group(1)
            health_url = base_url + "/health"
            response = requests.get(health_url, timeout=STATUS_TIMEOUT)

            if response.status_code == 200:
                detail = "Serveur accessible"
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        detail = data.get("status") or detail
                except (ValueError, TypeError):
                    pass
                model_name = "Modèle inconnu"
                try:
                    models_response = requests.get(
                        base_url + "/v1/models", timeout=STATUS_TIMEOUT
                    )
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        models = (
                            models_data.get("data", [])
                            if isinstance(models_data, dict)
                            else []
                        )
                        if models and isinstance(models[0], dict):
                            model_name = str(models[0].get("id") or model_name)
                except (
                    requests.exceptions.RequestException,
                    ValueError,
                    TypeError,
                    KeyError,
                ):
                    pass
                self.status_checked.emit(True, str(detail), model_name)
            elif response.status_code == 503:
                self.status_checked.emit(False, "Serveur en cours de chargement", "")
            else:
                self.status_checked.emit(
                    False, f"Réponse HTTP {response.status_code}", ""
                )
        except requests.exceptions.Timeout:
            self.status_checked.emit(False, "Délai de réponse dépassé", "")
        except requests.exceptions.ConnectionError:
            self.status_checked.emit(False, "Serveur inaccessible", "")
        except requests.exceptions.RequestException as error:
            self.status_checked.emit(False, f"Erreur réseau : {error}", "")
