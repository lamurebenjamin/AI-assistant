# -*- coding: utf-8 -*-
"""Thread de collecte globale des ressources (RAM processus, GPU, modèle) pour le dialogue d'information."""

import ctypes
import os
import re
import subprocess
import sys
from typing import Set

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from src.config.schema import STATUS_TIMEOUT


class RuntimeInfoThread(QThread):
    """Collecte les ressources de l'interface et du serveur llama.cpp géré."""

    info_ready = pyqtSignal(str)

    def __init__(self, api_url: str, process_ids: Set[int], parent=None):
        super().__init__(parent)
        self.api_url = api_url.strip()
        self.process_ids = {int(pid) for pid in process_ids if pid}

    @staticmethod
    def _format_memory(megabytes: float) -> str:
        if megabytes >= 1024:
            return f"{megabytes / 1024:.2f} Gio"
        return f"{megabytes:.0f} Mio"

    @staticmethod
    def _get_process_ram_mb(process_id: int) -> float:
        """Retourne le working set d'un processus Windows en Mio."""
        if sys.platform != "win32":
            if process_id != os.getpid():
                return 0.0
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return usage / 1024 if sys.platform != "darwin" else usage / (1024 * 1024)

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, process_id
        )
        if not handle:
            return 0.0
        try:
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            success = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            if not success:
                return 0.0
            return counters.WorkingSetSize / (1024 * 1024)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def _get_model_name(self) -> str:
        match = re.match(r"^(https?://[^/]+)", self.api_url)
        if not match:
            return "Indisponible"
        try:
            response = requests.get(
                match.group(1) + "/v1/models", timeout=STATUS_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data", []) if isinstance(payload, dict) else []
            if models and isinstance(models[0], dict):
                model_id = str(models[0].get("id") or "").strip()
                filename = os.path.basename(model_id.replace("\\", "/"))
                filename = re.sub(r"\.gguf$", "", filename, flags=re.IGNORECASE)
                if filename:
                    return filename[0].upper() + filename[1:]
        except (requests.exceptions.RequestException, ValueError, TypeError, KeyError):
            pass
        return "Indisponible"

    @staticmethod
    def _run_nvidia_smi(arguments):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        return subprocess.run(
            ["nvidia-smi", *arguments],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
            check=False,
        )

    def _get_gpu_information(self) -> dict:
        info = {
            "name": "Indisponible",
            "cuda": "Indisponible",
            "driver": "Indisponible",
            "temperature": "Indisponible",
            "pstate": "Indisponible",
            "vram": "Indisponible",
        }
        try:
            result = self._run_nvidia_smi([
                "--query-gpu=name,driver_version,temperature.gpu,pstate,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ])
            if result.returncode == 0:
                rows = []
                for line in result.stdout.splitlines():
                    values = [value.strip() for value in line.split(",")]
                    if len(values) >= 6:
                        rows.append(values[:6])
                if rows:
                    names, drivers, temperatures, pstates, vrams = [], [], [], [], []
                    for name, driver, temperature, pstate, used, total in rows:
                        names.append(name)
                        drivers.append(driver)
                        temperatures.append(f"{float(temperature):.0f} °C")
                        pstates.append(pstate.upper())
                        vrams.append(f"{float(used):.0f} Mio / {float(total):.0f} Mio")
                    info.update({
                        "name": " / ".join(names),
                        "driver": " / ".join(drivers),
                        "temperature": " / ".join(temperatures),
                        "pstate": " / ".join(pstates),
                        "vram": " / ".join(vrams),
                    })

            header = self._run_nvidia_smi([])
            if header.returncode == 0:
                match = re.search(
                    r"CUDA Version\s*:\s*([0-9]+(?:\.[0-9]+)?)",
                    header.stdout,
                    flags=re.IGNORECASE,
                )
                if match:
                    info["cuda"] = match.group(1)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
            pass
        return info

    def run(self):
        gpu = self._get_gpu_information()
        information = (
            f"Modèle : {self._get_model_name()}\n"
            f"Carte graphique : {gpu['name']}\n"
            f"CUDA : {gpu['cuda']}\n"
            f"Driver : {gpu['driver']}\n"
            f"Température : {gpu['temperature']}\n"
            f"État : {gpu['pstate']}\n"
            f"VRAM : {gpu['vram']}"
        )
        self.info_ready.emit(information)
