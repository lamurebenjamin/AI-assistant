# -*- coding: utf-8 -*-
"""Thread d'interrogation de nvidia-smi pour l'état du GPU, VRAM et températures."""

import subprocess
import sys
from PyQt5.QtCore import QThread, pyqtSignal


class NvidiaStatusThread(QThread):
    status_checked = pyqtSignal(bool, str, str)

    def run(self):
        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            command = [
                "nvidia-smi",
                "--query-gpu=name,pstate,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=creation_flags,
                check=False,
            )

            if result.returncode != 0:
                detail = (
                    (result.stderr or result.stdout).strip()
                    or "nvidia-smi a retourné une erreur"
                )
                self.status_checked.emit(False, "INDISPONIBLE", detail)
                return

            lines = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]
            if not lines:
                self.status_checked.emit(
                    False, "INDISPONIBLE", "Aucun GPU NVIDIA détecté"
                )
                return

            gpu_details = []
            pstates = []
            for index, line in enumerate(lines):
                values = [value.strip() for value in line.split(",")]
                if len(values) < 6:
                    continue
                name, pstate, utilization, memory_used, memory_total, temperature = (
                    values[:6]
                )
                pstates.append(pstate)
                prefix = f"GPU {index} - " if len(lines) > 1 else ""
                gpu_details.append(
                    f"{prefix}{name} | {utilization}% | "
                    f"VRAM {memory_used}/{memory_total} MiB | {temperature} °C"
                )

            if not gpu_details:
                self.status_checked.emit(
                    False, "INDISPONIBLE", "Réponse NVIDIA-SMI illisible"
                )
                return

            pstate_text = " / ".join(pstates)
            self.status_checked.emit(True, pstate_text, " ; ".join(gpu_details))

        except FileNotFoundError:
            self.status_checked.emit(False, "INDISPONIBLE", "nvidia-smi introuvable")
        except subprocess.TimeoutExpired:
            self.status_checked.emit(False, "INDISPONIBLE", "Délai NVIDIA-SMI dépassé")
        except OSError as error:
            self.status_checked.emit(False, "INDISPONIBLE", str(error))
