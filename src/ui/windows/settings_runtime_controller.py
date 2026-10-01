"""Supervision des etats serveur/GPU et arret des threads du dialogue."""
from src.monitoring.nvidia_status import NvidiaStatusThread
from src.monitoring.server_status import ServerStatusThread


def shutdown_background_threads(self):
    """Attend la fin des contrôles avant de détruire la boîte de dialogue."""
    self.status_timer.stop()

    if self.mic_test_thread is not None and self.mic_test_thread.isRunning():
        self.mic_test_thread.stop_recording()
        self.mic_test_thread.wait(2000)
    for thread in (self.status_thread, self.nvidia_thread):
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            # Les appels réseau ont un timeout maximal d'environ 5 secondes
            # et NVIDIA-SMI un timeout de 4 secondes.
            if not thread.wait(6500):
                # Dernier recours uniquement si un appel système reste bloqué.
                thread.terminate()
                thread.wait(1000)

    self.status_thread = None
    self.nvidia_thread = None


def refresh_runtime_status(self):
    self.check_server_status()
    self.check_nvidia_status()


def check_nvidia_status(self):
    if self.nvidia_thread is not None and self.nvidia_thread.isRunning():
        return
    self.gpu_pstate_label.setText("")
    self.gpu_detail_label.setText("")
    self.nvidia_thread = NvidiaStatusThread(self)
    self.nvidia_thread.status_checked.connect(self.update_nvidia_status)
    self.nvidia_thread.finished.connect(self.on_nvidia_thread_finished)
    self.nvidia_thread.start()


def on_nvidia_thread_finished(self):
    thread = self.sender()
    if thread is self.nvidia_thread:
        self.nvidia_thread = None
    thread.deleteLater()


def update_nvidia_status(self, available, pstate, detail):
    if available:
        descriptions = {
            "P0": "performances maximales",
            "P1": "performances élevées",
            "P2": "performances élevées",
            "P3": "performances intermédiaires",
            "P4": "performances intermédiaires",
            "P5": "performances intermédiaires",
            "P6": "faible activité",
            "P7": "faible activité",
            "P8": "repos / très faible consommation"
        }
        displayed_states = []
        for state in (item.strip() for item in pstate.split("/")):
            description = descriptions.get(state, "état de performance NVIDIA")
            displayed_states.append(f"{state} ({description})")
        self.gpu_pstate_label.setText("● " + " / ".join(displayed_states))
        high = any(
            state.strip() in ("P0", "P1", "P2") for state in pstate.split("/")
        )
        self.gpu_pstate_label.set_tone("success" if high else "info", weight=700)
        self.gpu_detail_label.setText(detail)
        self.gpu_detail_label.setToolTip(detail)
    else:
        self.gpu_pstate_label.setText("● INDISPONIBLE")
        self.gpu_pstate_label.set_tone("muted", weight=700)
        self.gpu_detail_label.setText("")
        self.gpu_detail_label.setToolTip("")


def schedule_server_status_check(self):
    # Redémarrer un timer unique évite des contrôles réseau obsolètes à chaque frappe.
    self.status_debounce_timer.start()


def check_server_status(self):
    if self.status_thread is not None and self.status_thread.isRunning():
        return
    self.server_status_label.setText("")
    self.server_status_detail.setText("")
    self.server_model_label.setText("INDISPONIBLE")
    self.status_thread = ServerStatusThread(
        self.api_input.text(), self, self._server_manager.auth_token
    )
    self.status_thread.status_checked.connect(self.update_server_status)
    self.status_thread.finished.connect(self.on_status_thread_finished)
    self.status_thread.start()


def on_status_thread_finished(self):
    thread = self.sender()
    if thread is self.status_thread:
        self.status_thread = None
    thread.deleteLater()


def update_server_status(self, online, detail, model_name):
    if online:
        self.server_status_label.setText("● EN LIGNE")
        self.server_status_label.set_tone("success", weight=700)
    else:
        self.server_status_label.setText("● HORS LIGNE")
        self.server_status_label.set_tone("danger", weight=700)
    # Ne pas afficher les messages techniques tels que « ok »,
    # « Vérification... » ou « Délai de réponse dépassé ».
    self.server_status_detail.setText("")
    self.server_model_label.setText(model_name if online and model_name else "INDISPONIBLE")
    self.server_model_label.setToolTip(
        model_name if online and model_name else "Aucun modèle détecté"
    )
