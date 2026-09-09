# -*- coding: utf-8 -*-
"""Assistant de bureau local basé sur PyQt5 et llama.cpp.

Le module gère l'interface graphique, les raccourcis clavier globaux,
l'enregistrement vocal et le cycle de vie du serveur local.
"""

import atexit
import math
import base64
import mimetypes
import copy
import ctypes
import html
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from src.platform.dll_loader import setup_nvidia_dll_directories
NVIDIA_DLL_HANDLES = setup_nvidia_dll_directories()

# Charge ONNX Runtime avant PyQt5 afin d'éviter les conflits de DLL. CUDA est
# sélectionné automatiquement lorsqu'il est disponible, sinon le CPU est utilisé.
try:
    import onnxruntime as ort

    KOKORO_AVAILABLE_PROVIDERS = tuple(ort.get_available_providers())
    if "CUDAExecutionProvider" in KOKORO_AVAILABLE_PROVIDERS:
        KOKORO_EXECUTION_PROVIDER = "CUDAExecutionProvider"
    else:
        KOKORO_EXECUTION_PROVIDER = "CPUExecutionProvider"

    from kokoro_onnx import Kokoro
except ModuleNotFoundError as error:
    if error.name in {"kokoro_onnx", "onnxruntime"}:
        raise RuntimeError(
            f"Le module {error.name!r} n'est pas installé dans "
            f"{sys.executable}. Exécutez : "
            f'"{sys.executable}" -m pip install -U kokoro-onnx onnxruntime-gpu'
        ) from error
    raise RuntimeError(
        "Une dépendance requise par Kokoro est introuvable : "
        f"{error.name!r}. Détail : {error}"
    ) from error
except ImportError as error:
    raise RuntimeError(
        "Échec du chargement initial de Kokoro ou ONNX Runtime : "
        f"{type(error).__name__}: {error}"
    ) from error

# Force les flux texte de la console Windows en UTF-8.
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

import keyboard
import numpy as np
import pyperclip
import requests
import sounddevice as sd
from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    QRectF,
    QPointF,
    QSize,
    QThread,
    QTimer,
    QUrl,
    QUrlQuery,
    Qt,
    pyqtSignal,
    pyqtProperty,
)
from PyQt5.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPalette,
    QPixmap,
    QRegion,
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOptionButton,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from scipy.signal import resample_poly
# Gestionnaire modulaire des skills (DOCX, PDF, Excel, etc.).
from core.skill_manager import SkillManager, SkillError

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ==========================================
# CONFIGURATION WINDOWS 11 ACRYLIC BLUR
# ==========================================
class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_uint)
    ]

class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_uint),
        ("Data", ctypes.POINTER(AccentPolicy)),
        ("SizeOfData", ctypes.c_int)
    ]

def apply_acrylic_blur(hwnd, color=0xA0F8F8F8):
    """Applique un fond acrylique blanc translucide sous Windows 10/11."""
    if sys.platform != 'win32':
        return False

    try:
        accent = AccentPolicy()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = color  # Format Windows : AABBGGRR (0x40 = ~25% d'opacité)
        accent.AccentFlags = 2
        accent.AnimationId = 0

        data = WindowCompositionAttributeData()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        result = ctypes.windll.user32.SetWindowCompositionAttribute(
            int(hwnd), ctypes.byref(data)
        )
        return bool(result)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def apply_rounded_corners(hwnd):
    """Active les coins arrondis natifs sous Windows 11."""
    if sys.platform != 'win32':
        return

    try:
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference)
        )
    except (AttributeError, OSError):
        pass


from src.platform.foreground import (
    ADOBE_PROCESS_NAMES,
    get_foreground_process_name,
    is_adobe_reader_foreground,
)


# ==========================================
# GÉNÉRATEUR D'ICÔNES SVG
# ==========================================
def create_svg_icon(svg_path, color="#FFFFFF", stroke_width=2):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">{svg_path}</svg>'
    renderer = QSvgRenderer(svg.encode('utf-8'))
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

ICONS = {}
ICONS_DARK = {}

def initialize_icons() -> None:
    global ICONS, ICONS_DARK
    ICONS = {
    "add": create_svg_icon('<path d="M12 5v14M5 12h14"/>'),
    "delete": create_svg_icon('<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'),
    "up": create_svg_icon('<path d="M18 15l-6-6-6 6"/>'),
    "down": create_svg_icon('<path d="M6 9l6 6 6-6"/>'),
    "save": create_svg_icon('<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>'),
    "cancel": create_svg_icon('<path d="M18 6L6 18M6 6l12 12"/>'),
    "settings": create_svg_icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/>'),
    "regenerate": create_svg_icon('<path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6.7 6.7L4 9M20 15l-2.7 2.3A7 7 0 0 1 5.5 15"/>'),
    # Deux carrés symétriques autour du centre exact du viewBox 24 x 24.
    "copy": create_svg_icon('<rect x="4" y="4" width="12" height="12" rx="2"/><rect x="8" y="8" width="12" height="12" rx="2"/>'),
    "check": create_svg_icon('<path d="M5 12.5l4.2 4.2L19 7"/>'),
    "close": create_svg_icon('<path d="M6 6l12 12M18 6L6 18"/>'),
        "speak": create_svg_icon('<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>'),
        "stop": create_svg_icon('<rect x="6" y="6" width="12" height="12" rx="1"/>')
}
    ICONS_DARK = {
        "add": create_svg_icon('<path d="M12 5v14M5 12h14"/>', "#111111"),
        "delete": create_svg_icon('<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>', "#111111"),
        "up": create_svg_icon('<path d="M18 15l-6-6-6 6"/>', "#111111"),
        "down": create_svg_icon('<path d="M6 9l6 6 6-6"/>', "#111111"),
        "save": create_svg_icon('<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>', "#111111"),
        "cancel": create_svg_icon('<path d="M18 6L6 18M6 6l12 12"/>', "#111111"),
        "copy": create_svg_icon('<rect x="4" y="4" width="12" height="12" rx="2"/><rect x="8" y="8" width="12" height="12" rx="2"/>', "#111111", 1.2),
        "check": create_svg_icon('<path d="M5 12.5l4.2 4.2L19 7"/>', "#111111", 2.2),
        "close": create_svg_icon('<path d="M6 6l12 12M18 6L6 18"/>', "#111111", 1.2),
        "speak": create_svg_icon('<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18 6a8.5 8.5 0 0 1 0 12"/>', "#111111", 1.6),
        "stop": create_svg_icon('<rect x="6" y="6" width="12" height="12" rx="1"/>', "#111111", 1.6)
    }

# ==========================================
# CONFIGURATION JSON
# ==========================================
from src.config.schema import (
    APP_DIR,
    CONFIG_FILE,
    HTTP_TIMEOUT,
    STATUS_TIMEOUT,
    LOGGER,
    LOG_FORMAT,
    DEFAULT_CONFIG,
)
from src.config.manager import load_config, save_config
from src.llm.response_parser import (
    clean_chunk,
    split_thinking_and_answer,
    parse_audio_response,
)
from src.rendering.markdown import (
    format_inline_markdown,
    markdown_to_html,
    markdown_to_spoken_text,
)



# ==========================================
# PROCESSUS LOCAL LLAMA.CPP
# ==========================================
class LlamaServerManager:
    def __init__(self):
        self.process = None
        self.log_handle = None

    def _path(self, value):
        value = os.path.expandvars(os.path.expanduser(str(value).strip().strip('"')))
        if not os.path.isabs(value):
            value = os.path.join(os.path.dirname(os.path.abspath(__file__)), value)
        return os.path.normpath(value)

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, config):
        if self.is_running():
            return True, "Serveur déjà démarré"
        cfg = config.get('llama_server', {})
        exe = self._path(cfg.get('executable', 'llama-server.exe'))
        model = self._path(cfg.get('model', ''))
        if not os.path.isfile(exe):
            return False, f"Exécutable introuvable : {exe}"
        if not os.path.isfile(model):
            return False, f"Modèle introuvable : {model}"
        command = [exe, '-m', model] + [str(x) for x in cfg.get('arguments', [])]
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llama-server.log')
            self.log_handle = open(log_path, 'a', encoding='utf-8', buffering=1)
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            self.process = subprocess.Popen(command, cwd=os.path.dirname(exe), stdout=self.log_handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)
            return True, f"Démarrage en cours, PID {self.process.pid}"
        except (OSError, ValueError) as error:
            self.process = None
            if self.log_handle:
                self.log_handle.close()
                self.log_handle = None
            return False, str(error)

    def stop(self):
        if not self.is_running():
            self.process = None
            if self.log_handle:
                self.log_handle.close()
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
                self.log_handle.close()
                self.log_handle = None

LLAMA_SERVER_MANAGER = LlamaServerManager()
atexit.register(LLAMA_SERVER_MANAGER.stop)

# ==========================================
# VÉRIFICATION DU SERVEUR LLAMA.CPP
# ==========================================
class ServerStatusThread(QThread):
    status_checked = pyqtSignal(bool, str, str)

    def __init__(self, api_url, parent=None):
        super().__init__(parent)
        self.api_url = api_url.strip()

    def run(self):
        try:
            # L'API de génération se termine généralement par /v1/chat/completions.
            # llama.cpp expose son état sur /health.
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
                        models = models_data.get("data", []) if isinstance(models_data, dict) else []
                        if models and isinstance(models[0], dict):
                            model_name = str(models[0].get("id") or model_name)
                except (requests.exceptions.RequestException, ValueError, TypeError, KeyError):
                    pass
                self.status_checked.emit(True, str(detail), model_name)
            elif response.status_code == 503:
                self.status_checked.emit(False, "Serveur en cours de chargement", "")
            else:
                self.status_checked.emit(False, f"Réponse HTTP {response.status_code}", "")
        except requests.exceptions.Timeout:
            self.status_checked.emit(False, "Délai de réponse dépassé", "")
        except requests.exceptions.ConnectionError:
            self.status_checked.emit(False, "Serveur inaccessible", "")
        except requests.exceptions.RequestException as error:
            self.status_checked.emit(False, f"Erreur réseau : {error}", "")

# ==========================================
# INFORMATIONS NVIDIA-SMI
# ==========================================
class NvidiaStatusThread(QThread):
    status_checked = pyqtSignal(bool, str, str)

    def run(self):
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            command = [
                "nvidia-smi",
                "--query-gpu=name,pstate,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=creation_flags,
                check=False
            )

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip() or "nvidia-smi a retourné une erreur"
                self.status_checked.emit(False, "INDISPONIBLE", detail)
                return

            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if not lines:
                self.status_checked.emit(False, "INDISPONIBLE", "Aucun GPU NVIDIA détecté")
                return

            gpu_details = []
            pstates = []
            for index, line in enumerate(lines):
                values = [value.strip() for value in line.split(',')]
                if len(values) < 6:
                    continue
                name, pstate, utilization, memory_used, memory_total, temperature = values[:6]
                pstates.append(pstate)
                prefix = f"GPU {index} - " if len(lines) > 1 else ""
                gpu_details.append(
                    f"{prefix}{name} | {utilization}% | "
                    f"VRAM {memory_used}/{memory_total} MiB | {temperature} °C"
                )

            if not gpu_details:
                self.status_checked.emit(False, "INDISPONIBLE", "Réponse NVIDIA-SMI illisible")
                return

            pstate_text = " / ".join(pstates)
            self.status_checked.emit(True, pstate_text, " ; ".join(gpu_details))

        except FileNotFoundError:
            self.status_checked.emit(False, "INDISPONIBLE", "nvidia-smi introuvable")
        except subprocess.TimeoutExpired:
            self.status_checked.emit(False, "INDISPONIBLE", "Délai NVIDIA-SMI dépassé")
        except OSError as error:
            self.status_checked.emit(False, "INDISPONIBLE", str(error))

# ==========================================
# INFORMATIONS D'EXÉCUTION POUR L'ICÔNE SYSTÈME
# ==========================================
class RuntimeInfoThread(QThread):
    """Collecte les ressources de l'interface et du serveur llama.cpp géré."""

    info_ready = pyqtSignal(str)

    def __init__(self, api_url, process_ids, parent=None):
        super().__init__(parent)
        self.api_url = api_url.strip()
        self.process_ids = {int(pid) for pid in process_ids if pid}

    @staticmethod
    def _format_memory(megabytes):
        if megabytes >= 1024:
            return f"{megabytes / 1024:.2f} Gio"
        return f"{megabytes:.0f} Mio"

    @staticmethod
    def _get_process_ram_mb(process_id):
        """Retourne le working set d'un processus Windows en Mio."""
        if sys.platform != "win32":
            # Ce repli mesure uniquement le processus Python courant hors Windows.
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

    def _get_model_name(self):
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
                # Accepte les chemins Windows et Unix, puis retire uniquement l'extension GGUF.
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

    def _get_gpu_information(self):
        """Récupère les informations demandées directement depuis nvidia-smi."""
        info = {
            "name": "Indisponible",
            "cuda": "Indisponible",
            "driver": "Indisponible",
            "temperature": "Indisponible",
            "pstate": "Indisponible",
            "vram": "Indisponible",
        }
        try:
            # Requête CSV fiable et indépendante de la mise en page du tableau nvidia-smi.
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

            # La version CUDA figure dans l'en-tête de la sortie standard de nvidia-smi.
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


class RuntimeInfoDialog(QDialog):
    """Fenêtre compacte affichant les ressources de l'application."""

    WINDOW_WIDTH = 520
    MINIMUM_HEIGHT = 110
    MAXIMUM_HEIGHT = 220

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assistant IA")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.setAutoFillBackground(True)
        light_palette = self.palette()
        light_palette.setColor(QPalette.Window, QColor("#F8FAFC"))
        light_palette.setColor(QPalette.WindowText, QColor("#17202A"))
        light_palette.setColor(QPalette.Base, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.Text, QColor("#17202A"))
        self.setPalette(light_palette)
        self.setStyleSheet(
            "QDialog { background:#F8FAFC; }"
            "QLabel#RuntimeValues { color:#17202A; font-size:13px; "
            "background:#FFFFFF; border:1px solid #CBD7E4; border-radius:7px; "
            "padding:14px; }"
        )
        self.runtime_layout = QVBoxLayout(self)
        self.runtime_layout.setContentsMargins(18, 16, 18, 16)

        self.values_label = QLabel("Collecte des informations...")
        self.values_label.setObjectName("RuntimeValues")
        self.values_label.setWordWrap(True)
        self.values_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.runtime_layout.addWidget(self.values_label)
        self._adjust_height_to_content()

    def _adjust_height_to_content(self):
        """Adapte la hauteur au contenu tout en conservant un format compact."""
        self.runtime_layout.activate()
        content_height = self.runtime_layout.sizeHint().height()
        target_height = max(
            self.MINIMUM_HEIGHT,
            min(content_height, self.MAXIMUM_HEIGHT),
        )
        self.setFixedHeight(target_height)

    def set_information(self, information):
        self.values_label.setText(information)
        self.values_label.adjustSize()
        self._adjust_height_to_content()


# ==========================================
# FENÊTRE DES PARAMÈTRES (Harmonisée Acrylique)
# ==========================================
class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.temp_actions = [a.copy() for a in config['actions']]
        self.temp_api_url = config['api_url']
        self.temp_voice_config = copy.deepcopy(config.get('voice_input', DEFAULT_CONFIG['voice_input']))
        self.temp_tts_config = copy.deepcopy(config.get('text_to_speech', DEFAULT_CONFIG['text_to_speech']))
        self.mic_test_thread = None
        self.temp_server_config = config.get('llama_server', {}).copy()
        self.temp_server_config['arguments'] = list(self.temp_server_config.get('arguments', []))
        self.is_updating_ui = False
        self.drag_position = None
        self.status_thread = None
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(5000)
        self.status_timer.timeout.connect(self.refresh_runtime_status)
        self.status_debounce_timer = QTimer(self)
        self.status_debounce_timer.setSingleShot(True)
        self.status_debounce_timer.setInterval(500)
        self.status_debounce_timer.timeout.connect(self.check_server_status)
        self.nvidia_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        # Fenêtre Paramètres volontairement opaque. Une fenêtre native translucide
        # avec effet Acrylic peut parfois perdre les clics dans sa zone cliente
        # sous Windows, alors que la barre de titre continue de fonctionner.
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.setAutoFillBackground(True)
        # Largeur fixe ; la hauteur sera ajustée au contenu une fois
        # l'ensemble des onglets et des boutons construit.
        self.setFixedWidth(840)

        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QTabWidget::pane {
                background: #F8FAFC;
                border: 1px solid #CBD7E4;
                border-top: none;
                border-radius: 0 0 8px 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #E9EEF4;
                color: #4B5563;
                border: 1px solid #CBD7E4;
                border-bottom: none;
                padding: 9px 18px;
                margin-right: 3px;
                min-width: 110px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #F8FAFC;
                color: #171717;
            }
            QTabBar::tab:hover:!selected { background: #DDE6F0; }
            QFrame#AcrylicPanel {
                background-color: #F8FAFC;
                border: 1px solid #CBD7E4;
                border-radius: 16px;
            }
            QFrame#Header {
                background-color: transparent;
                border: none;
            }
            QLabel#TitleLabel {
                background: transparent; color: #171717; border: none; padding: 0;
                font-family: 'Aptos Display', 'Segoe UI Variable Display', 'Segoe UI', Arial; font-size: 13px; font-weight: 700;
            }
            QPushButton#CloseButton {
                background-color: transparent; border: none; border-radius: 14px;
                padding: 0; margin: 0; text-align: center;
            }
            QPushButton#CloseButton:hover, QPushButton#CloseButton:pressed,
            QPushButton#CloseButton:focus { background: transparent; border: none; outline: none; }
            QPushButton#ToolButton:hover { background-color: rgba(0, 0, 0, 12); }
            QPushButton#ToolButton {
                background-color: transparent; border: none; border-radius: 14px; padding: 3px;
            }
            QPushButton#ToolButton:disabled { background-color: transparent; }
            QLabel { color: #111111; background: transparent; }
            QLineEdit, QTextEdit, QComboBox {
                background-color: rgba(255, 255, 255, 245); border: 1px solid rgba(8, 74, 144, 70);
                border-radius: 4px; padding: 6px; color: #111111;
            }
            QListWidget {
                background-color: rgba(255, 255, 255, 245); border: 1px solid rgba(8, 74, 144, 70);
                border-radius: 6px; padding: 4px; outline: none; color: #111111;
            }
            QListWidget::item { padding: 6px; border-radius: 4px; }
            QListWidget::item:hover { background-color: rgba(0, 0, 0, 20); }
            QListWidget::item:selected { background-color: #2563B8; color: #FFFFFF; }
            QPushButton {
                background-color: rgba(255, 255, 255, 100); border: 1px solid rgba(0, 0, 0, 50);
                border-radius: 6px; padding: 6px 12px; color: #111111;
            }
            QPushButton:hover { background-color: rgba(0, 0, 0, 10); }
            QPushButton:pressed { background-color: rgba(0, 0, 0, 20); }
            QPushButton#CancelBtn {
                background-color: #FFFFFF; color: #303640; border: 1px solid #C5D0DC;
                border-radius: 8px; padding: 7px 16px; font-weight: 600;
            }
            QPushButton#CancelBtn:hover { background-color: #F1F5F9; border-color: #AAB8C7; }
            QPushButton#CancelBtn:pressed { background-color: #E6EDF4; }
            QPushButton#SaveBtn {
                background-color: #2563B8; color: #FFFFFF; border: 1px solid #2563B8;
                border-radius: 8px; padding: 7px 18px; font-weight: 600;
            }
            QPushButton#SaveBtn:hover { background-color: #1D4F96; border-color: #1D4F96; }
            QPushButton#SaveBtn:pressed { background-color: #173F78; border-color: #173F78; }
            QScrollArea, QScrollArea QWidget, QScrollArea QViewport { background: transparent; border: none; }
            QScrollBar:vertical { background: rgba(0, 0, 0, 14); width: 10px; margin: 4px 3px 8px 0; border-radius: 5px; }
            QScrollBar::handle:vertical { background: rgba(30, 30, 30, 85); min-height: 26px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: rgba(30, 30, 30, 135); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: transparent; }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.header = QFrame(self.panel)
        self.header.setObjectName("Header")
        self.header.setFixedHeight(36)
        self.header.setMouseTracking(True)
        self.header.installEventFilter(self)
        header = self.header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 1, 3, 0)
        header_layout.setSpacing(3)
        header_layout.setAlignment(Qt.AlignVCenter)

        self.header_icon_label = QLabel(header)
        self.header_icon_label.setFixedSize(18, 18)
        self.header_icon_label.setAlignment(Qt.AlignCenter)
        header_icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assistant_icon.webp"
        )
        header_icon = QIcon(header_icon_path)
        if header_icon.isNull():
            fallback_svg = (
                '<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 '
                'C7.5 12.8 11.2 16.5 12 22.5 '
                'C12.8 16.5 16.5 12.8 22.5 12 '
                'C16.5 11.2 12.8 7.5 12 1.5z"/>'
            )
            header_icon = create_svg_icon(fallback_svg, "#171717")
        self.header_icon_label.setPixmap(header_icon.pixmap(16, 16))
        header_layout.addWidget(self.header_icon_label, 0, Qt.AlignVCenter)

        title_label = QLabel("Paramètres", header)
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setTextFormat(Qt.PlainText)
        header_layout.addWidget(title_label, 1)

        close_btn = QPushButton(header)
        close_btn.setObjectName("CloseButton")
        close_btn.setFlat(True)
        close_btn.setAutoFillBackground(False)
        close_btn.setIcon(ICONS_DARK["close"])
        close_btn.setIconSize(QSize(19, 19))
        close_btn.setFixedSize(27, 28)
        close_btn.setToolTip("Fermer")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn, 0, Qt.AlignVCenter)
        panel_layout.addWidget(header)

        separator_container = QWidget(self.panel)
        separator_container.setFixedHeight(3)
        separator_layout = QHBoxLayout(separator_container)
        separator_layout.setContentsMargins(14, 0, 14, 0)
        separator = QFrame(separator_container)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(0,0,0,35); border: none;")
        separator_layout.addWidget(separator)
        panel_layout.addWidget(separator_container)

        content_widget = QWidget(self.panel)
        content_widget.setObjectName("SettingsContent")
        content_widget.setEnabled(True)
        content_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        content_widget.setAttribute(Qt.WA_NoSystemBackground, False)
        content_widget.setAutoFillBackground(True)
        content_widget.setStyleSheet("QWidget#SettingsContent { background-color: #F8FAFC; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(22, 18, 22, 18)
        content_layout.setSpacing(12)

        # Organisation des paramètres par domaine fonctionnel.
        self.settings_tabs = QTabWidget(content_widget)
        self.settings_tabs.setDocumentMode(True)

        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        llm_layout.setContentsMargins(10, 12, 10, 10)
        llm_layout.setSpacing(12)

        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        voice_layout.setContentsMargins(10, 12, 10, 10)
        voice_layout.setSpacing(12)

        shortcuts_tab = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_tab)
        shortcuts_layout.setContentsMargins(10, 12, 10, 10)
        shortcuts_layout.setSpacing(12)

        self.settings_tabs.addTab(llm_tab, "LLM")
        self.settings_tabs.addTab(voice_tab, "Assistant vocal")
        self.settings_tabs.addTab(shortcuts_tab, "Raccourcis")
        content_layout.addWidget(self.settings_tabs, 1)

        # URL, état du serveur et modèle affichés sur trois lignes distinctes.
        api_line_layout = QHBoxLayout()
        api_line_layout.setSpacing(8)
        status_line_layout = QHBoxLayout()
        status_line_layout.setSpacing(8)
        model_line_layout = QHBoxLayout()
        model_line_layout.setSpacing(8)

        api_label = QLabel("URL API llama.cpp")
        api_label.setStyleSheet("font-weight: bold;")

        self.api_input = QLineEdit(self.temp_api_url)
        self.api_input.setFixedHeight(34)
        self.api_input.setMinimumWidth(250)
        self.api_input.textChanged.connect(self.schedule_server_status_check)

        status_title = QLabel("État du serveur :")
        status_title.setStyleSheet("font-weight: 600; color: #303640;")
        status_title.setSizePolicy(status_title.sizePolicy().Fixed, status_title.sizePolicy().Preferred)

        self.server_status_label = QLabel("")
        self.server_status_label.setStyleSheet("color: #C47F00; font-weight: 600;")
        self.server_status_label.setSizePolicy(
            self.server_status_label.sizePolicy().Fixed,
            self.server_status_label.sizePolicy().Preferred
        )

        self.server_status_detail = QLabel("")
        self.server_status_detail.setStyleSheet("color: #69717D;")
        self.server_status_detail.setSizePolicy(
            self.server_status_detail.sizePolicy().Fixed,
            self.server_status_detail.sizePolicy().Preferred
        )

        model_title = QLabel("Modèle LLM :")
        model_title.setStyleSheet("font-weight: 600; color: #303640;")
        self.server_model_label = QLabel("INDISPONIBLE")
        self.server_model_label.setStyleSheet("color: #2563B8; font-weight: 600;")
        self.server_model_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.server_model_label.setToolTip("Modèle déclaré par l'endpoint /v1/models")

        api_line_layout.addWidget(api_label)
        api_line_layout.addWidget(self.api_input, 1)
        llm_layout.addLayout(api_line_layout)

        status_line_layout.addWidget(status_title)
        status_line_layout.addWidget(self.server_status_label)
        status_line_layout.addWidget(self.server_status_detail)
        status_line_layout.addStretch(1)
        llm_layout.addLayout(status_line_layout)

        model_line_layout.addWidget(model_title)
        model_line_layout.addWidget(self.server_model_label)
        model_line_layout.addStretch(1)
        llm_layout.addLayout(model_line_layout)

        server_box = QFrame()
        server_box.setStyleSheet("QFrame { background:#EEF3F8; border:1px solid #CBD7E4; border-radius:6px; }")
        server_form = QFormLayout(server_box)
        server_form.setContentsMargins(12, 10, 12, 10)
        server_form.setSpacing(8)
        self.server_exe_input = QLineEdit(self.temp_server_config.get('executable', 'llama-server.exe'))
        self.server_model_input = QLineEdit(self.temp_server_config.get('model', ''))
        self.server_args_input = QTextEdit()
        self.server_args_input.setPlainText("\n".join(self.temp_server_config.get('arguments', [])))
        self.server_args_input.setFixedHeight(125)
        self.server_args_input.setToolTip("Un argument par ligne")
        self.server_autostart_check = QCheckBox("Démarrer automatiquement avec l'application")
        self.server_autostart_check.setChecked(bool(self.temp_server_config.get('auto_start', True)))
        exe_row = QHBoxLayout(); exe_row.addWidget(self.server_exe_input, 1)
        exe_btn = QPushButton("Parcourir"); exe_btn.clicked.connect(self.browse_server_executable); exe_row.addWidget(exe_btn)
        model_row = QHBoxLayout(); model_row.addWidget(self.server_model_input, 1)
        model_btn = QPushButton("Parcourir"); model_btn.clicked.connect(self.browse_server_model); model_row.addWidget(model_btn)
        process_row = QHBoxLayout()
        self.server_process_status = QLabel("PROCESSUS DÉMARRÉ" if LLAMA_SERVER_MANAGER.is_running() else "PROCESSUS ARRÊTÉ")
        process_row.addWidget(self.server_process_status, 1)
        start_btn = QPushButton("Démarrer"); start_btn.clicked.connect(self.start_local_server)
        stop_btn = QPushButton("Arrêter"); stop_btn.clicked.connect(self.stop_local_server)
        process_row.addWidget(start_btn); process_row.addWidget(stop_btn)
        server_form.addRow("Exécutable", exe_row)
        server_form.addRow("Modèle GGUF", model_row)
        server_form.addRow("Arguments", self.server_args_input)
        server_form.addRow("", self.server_autostart_check)
        server_form.addRow("Processus", process_row)
        llm_layout.addWidget(server_box)

        # État du GPU sur une seule ligne, sans libellé superflu.
        gpu_line_layout = QHBoxLayout()
        gpu_line_layout.setSpacing(8)

        self.gpu_pstate_label = QLabel("")
        self.gpu_pstate_label.setStyleSheet("color: #C47F00; font-weight: 700;")
        self.gpu_detail_label = QLabel("")
        self.gpu_detail_label.setStyleSheet("color: #69717D;")
        self.gpu_detail_label.setToolTip("Nom du GPU, utilisation, VRAM et température")
        gpu_line_layout.addWidget(self.gpu_pstate_label)
        gpu_line_layout.addWidget(self.gpu_detail_label, 1)
        llm_layout.addLayout(gpu_line_layout)

        voice_box = QFrame()
        voice_box.setStyleSheet("QFrame { background:#EEF3F8; border:1px solid #CBD7E4; border-radius:6px; }")
        voice_form = QFormLayout(voice_box)
        voice_form.setContentsMargins(12, 10, 12, 10)

        self.automatic_reading_check = QCheckBox("Lire automatiquement les réponses à haute voix")
        self.automatic_reading_check.setChecked(
            bool(self.temp_tts_config.get("automatic_reading", False))
        )
        self.automatic_reading_check.setToolTip(
            "Démarre automatiquement la lecture vocale lorsqu’une réponse est terminée."
        )
        voice_form.addRow("Lecture vocale", self.automatic_reading_check)

        # Le mode vocal reste configure en arriere-plan, sans case visible.
        self.voice_enabled_check = QCheckBox()
        self.voice_enabled_check.setChecked(bool(self.temp_voice_config.get("enabled", True)))
        self.voice_enabled_check.hide()

        device_row = QHBoxLayout()
        self.voice_device_combo = QComboBox()
        self.voice_refresh_btn = QPushButton("Actualiser les périphériques")
        self.voice_refresh_btn.clicked.connect(self.refresh_audio_devices)
        device_row.addWidget(self.voice_device_combo, 1)
        device_row.addWidget(self.voice_refresh_btn)
        voice_form.addRow(device_row)

        test_row = QHBoxLayout()
        self.voice_test_btn = QPushButton("Tester le microphone")
        self.voice_test_btn.clicked.connect(self.toggle_microphone_test)
        self.voice_test_level = QProgressBar()
        self.voice_test_level.setRange(0, 100)
        self.voice_test_level.setTextVisible(False)
        test_row.addWidget(self.voice_test_btn)
        test_row.addWidget(self.voice_test_level, 1)
        voice_form.addRow(test_row)

        # Conserve le retour d'erreur sans afficher de rectangle supplementaire.
        self.voice_device_info = QLabel("")
        self.voice_device_info.hide()
        voice_layout.addWidget(voice_box)
        voice_layout.addStretch(1)
        self.refresh_audio_devices()

        info_label = QLabel("Astuce : Ctrl+1 à Ctrl+9 utilisent le texte sélectionné. Ctrl+Alt+1 à Ctrl+Alt+9 utilisent la voix avec la même action.")
        info_label.setStyleSheet("color: #5B6470; font-size: 12px; font-style: italic;")
        info_label.setWordWrap(True)
        shortcuts_layout.addWidget(info_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(145)
        self.list_widget.currentRowChanged.connect(self.on_action_selected)
        actions_layout.addWidget(self.list_widget, 1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        btn_add = QPushButton(" Ajouter"); btn_add.setIcon(ICONS_DARK["add"]); btn_add.clicked.connect(self.add_action)
        btn_del = QPushButton(" Supprimer"); btn_del.setIcon(ICONS_DARK["delete"]); btn_del.clicked.connect(self.del_action)
        btn_up = QPushButton(); btn_up.setIcon(ICONS_DARK["up"]); btn_up.setToolTip("Monter"); btn_up.clicked.connect(lambda: self.move_action(-1))
        btn_down = QPushButton(); btn_down.setIcon(ICONS_DARK["down"]); btn_down.setToolTip("Descendre"); btn_down.clicked.connect(lambda: self.move_action(1))

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        actions_layout.addLayout(btn_layout, 0)
        shortcuts_layout.addLayout(actions_layout, 1)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(34)
        self.sys_prompt_input = QTextEdit()
        self.sys_prompt_input.setMinimumHeight(115)
        self.prefix_input = QLineEdit()
        self.prefix_input.setFixedHeight(34)

        self.name_input.textChanged.connect(self.update_action_field)
        self.sys_prompt_input.textChanged.connect(self.update_action_field)
        self.prefix_input.textChanged.connect(self.update_action_field)

        form_layout.addRow("Nom du raccourcis", self.name_input)
        form_layout.addRow("Prompt Système", self.sys_prompt_input)
        form_layout.addRow("Préfixe", self.prefix_input)
        shortcuts_layout.addLayout(form_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.setIcon(ICONS_DARK["cancel"])
        btn_cancel.setIconSize(QSize(16, 16))
        btn_cancel.setMinimumHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Sauvegarder")
        btn_save.setObjectName("SaveBtn")
        btn_save.setIcon(ICONS["save"])
        btn_save.setIconSize(QSize(16, 16))
        btn_save.setMinimumHeight(38)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)

        bottom_layout.addWidget(btn_cancel)
        bottom_layout.addWidget(btn_save)
        content_layout.addLayout(bottom_layout)

        panel_layout.addWidget(content_widget)

        self.main_layout.addWidget(self.panel)
        self.panel.setEnabled(True)
        content_widget.setEnabled(True)
        self.populate_list()
        self.api_input.setFocus(Qt.OtherFocusReason)

        # Ajuste la hauteur de la fenêtre au contenu réel, tout en la limitant
        # à la hauteur disponible de l'écran.
        self.main_layout.activate()
        content_height = self.sizeHint().height()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        maximum_height = max(400, screen.availableGeometry().height() - 40)
        self.setFixedHeight(min(content_height, maximum_height))

    def eventFilter(self, watched, event):
        # Le déplacement est limité à l'en-tête. Sous Windows, le déplacement
        # natif est utilisé afin d'éviter les traces de repeinture et les widgets
        # dupliqués visuellement pendant le glissement.
        if watched is self.header:
            if event.type() == event.MouseButtonDblClick:
                event.accept()
                return True

            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                if sys.platform == 'win32':
                    try:
                        WM_NCLBUTTONDOWN = 0x00A1
                        HTCAPTION = 0x0002
                        hwnd = int(self.winId())
                        ctypes.windll.user32.ReleaseCapture()
                        ctypes.windll.user32.SendMessageW(
                            hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0
                        )
                    except (AttributeError, OSError, TypeError, ValueError):
                        self.drag_position = (
                            event.globalPos() - self.frameGeometry().topLeft()
                        )
                else:
                    self.drag_position = (
                        event.globalPos() - self.frameGeometry().topLeft()
                    )
                event.accept()
                return True

            # Repli uniquement pour les plateformes sans déplacement natif.
            if (sys.platform != 'win32' and
                    event.type() == event.MouseMove and
                    self.drag_position is not None and
                    event.buttons() & Qt.LeftButton):
                self.move(event.globalPos() - self.drag_position)
                event.accept()
                return True

            if event.type() == event.MouseButtonRelease:
                self.drag_position = None
                self.repaint()
                self.panel.repaint()
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        # Une mise à jour différée évite les restes visuels après déplacement.
        QTimer.singleShot(0, self.update)

    def showEvent(self, event):
        super().showEvent(event)
        self.drag_position = None
        self.panel.setEnabled(True)
        self.panel.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Centre toujours la fenêtre sur l'écran actif pour éviter les affichages
        # partiels ou hors écran, notamment avec plusieurs moniteurs.
        parent = self.parentWidget()
        if parent is not None:
            screen = QApplication.screenAt(parent.frameGeometry().center())
        else:
            screen = QApplication.screenAt(QCursor.pos())
        screen = screen or QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(
            available.x() + (available.width() - self.width()) // 2,
            available.y() + (available.height() - self.height()) // 2
        )

        QTimer.singleShot(0, self.apply_effects)
        QTimer.singleShot(100, self.refresh_runtime_status)
        self.status_timer.start()

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

    def done(self, result):
        # done() est appelé par Fermer, Annuler, Sauvegarder et reject().
        self.shutdown_background_threads()
        super().done(result)

    def closeEvent(self, event):
        self.shutdown_background_threads()
        super().closeEvent(event)

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
            color = "#16833B" if any(
                state.strip() in ("P0", "P1", "P2") for state in pstate.split("/")
            ) else "#2563B8"
            self.gpu_pstate_label.setStyleSheet(f"color: {color}; font-weight: 700;")
            self.gpu_detail_label.setText(detail)
            self.gpu_detail_label.setToolTip(detail)
        else:
            # Aucun texte temporaire ou message technique de vérification.
            self.gpu_pstate_label.setText("● INDISPONIBLE")
            self.gpu_pstate_label.setStyleSheet("color: #69717D; font-weight: 700;")
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
        self.status_thread = ServerStatusThread(self.api_input.text(), self)
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
            self.server_status_label.setStyleSheet("color: #16833B; font-weight: 700;")
        else:
            self.server_status_label.setText("● HORS LIGNE")
            self.server_status_label.setStyleSheet("color: #C62828; font-weight: 700;")
        # Ne pas afficher les messages techniques tels que « ok »,
        # « Vérification... » ou « Délai de réponse dépassé ».
        self.server_status_detail.setText("")
        self.server_model_label.setText(model_name if online and model_name else "INDISPONIBLE")
        self.server_model_label.setToolTip(
            model_name if online and model_name else "Aucun modèle détecté"
        )

    def apply_effects(self):
        # Pas d'Acrylic dans Paramètres : cela garantit que toute la zone cliente
        # reste interactive de manière fiable sous Windows 10/11.
        hwnd = int(self.winId())
        apply_rounded_corners(hwnd)
        self.raise_()
        self.activateWindow()

    def populate_list(self):
        self.is_updating_ui = True
        self.list_widget.clear()
        for i, action in enumerate(self.temp_actions):
            display_name = action['name']
            if i < 9:
                display_name = f"{i+1}  •  {display_name}"
            self.list_widget.addItem(display_name)
        self.is_updating_ui = False
        if self.temp_actions:
            self.list_widget.setCurrentRow(0)

    def on_action_selected(self, row):
        if self.is_updating_ui or row < 0: return
        self.is_updating_ui = True
        action = self.temp_actions[row]
        self.name_input.setText(action['name'])
        self.sys_prompt_input.setText(action['system_prompt'])
        self.prefix_input.setText(action['prompt_prefix'])
        self.is_updating_ui = False

    def update_action_field(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        if row >= 0:
            self.temp_actions[row]['name'] = self.name_input.text()
            self.temp_actions[row]['system_prompt'] = self.sys_prompt_input.toPlainText()
            self.temp_actions[row]['prompt_prefix'] = self.prefix_input.text()

            display_name = self.name_input.text()
            if row < 9:
                display_name = f"{row+1}  •  {display_name}"
            self.list_widget.item(row).setText(display_name)

    def add_action(self):
        self.temp_actions.append({"name": "Nouvelle Action", "system_prompt": "Tu es un assistant IA.", "prompt_prefix": ""})
        self.populate_list()
        self.list_widget.setCurrentRow(len(self.temp_actions) - 1)

    def del_action(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            del self.temp_actions[row]
            self.populate_list()

    def move_action(self, direction):
        row = self.list_widget.currentRow()
        if 0 <= row + direction < len(self.temp_actions):
            self.temp_actions[row], self.temp_actions[row + direction] = self.temp_actions[row + direction], self.temp_actions[row]
            self.populate_list()
            self.list_widget.setCurrentRow(row + direction)

    def browse_server_executable(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner llama-server.exe", "", "Exécutable (*.exe);;Tous les fichiers (*)")
        if path: self.server_exe_input.setText(path)

    def browse_server_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le modèle GGUF", "", "Modèle GGUF (*.gguf);;Tous les fichiers (*)")
        if path: self.server_model_input.setText(path)

    def collect_server_config(self):
        return {'auto_start': self.server_autostart_check.isChecked(), 'executable': self.server_exe_input.text().strip(), 'model': self.server_model_input.text().strip(), 'arguments': [line.strip() for line in self.server_args_input.toPlainText().splitlines() if line.strip()]}

    def start_local_server(self):
        runtime = dict(self.config); runtime['llama_server'] = self.collect_server_config()
        ok, message = LLAMA_SERVER_MANAGER.start(runtime)
        self.server_process_status.setText("PROCESSUS DÉMARRÉ" if ok else "ÉCHEC DU DÉMARRAGE")
        self.server_process_status.setStyleSheet("font-weight:700;color:#16833B;" if ok else "font-weight:700;color:#C62828;")
        self.server_process_status.setToolTip(message)
        QTimer.singleShot(800, self.refresh_runtime_status)

    def stop_local_server(self):
        ok, message = LLAMA_SERVER_MANAGER.stop()
        self.server_process_status.setText("PROCESSUS ARRÊTÉ" if ok else "ÉCHEC DE L'ARRÊT")
        self.server_process_status.setStyleSheet("font-weight:700;color:#69717D;" if ok else "font-weight:700;color:#C62828;")
        self.server_process_status.setToolTip(message)
        QTimer.singleShot(250, self.refresh_runtime_status)

    def refresh_audio_devices(self):
        saved_name = self.temp_voice_config.get("input_device_name", "")
        self.voice_device_combo.clear()
        self.voice_device_combo.addItem("Périphérique par défaut de Windows", None)
        try:
            devices = sd.query_devices()
            for index, device in enumerate(devices):
                if int(device.get("max_input_channels", 0)) > 0:
                    name = str(device.get("name", f"Microphone {index}"))
                    self.voice_device_combo.addItem(name, {"index": index, "name": name})
            match = self.voice_device_combo.findText(saved_name, Qt.MatchExactly) if saved_name else 0
            if match < 0:
                match = 0
                self.voice_device_info.setText("Le microphone enregistré est indisponible. Le périphérique Windows par défaut sera utilisé.")
            else:
                self.voice_device_info.setText("")
            self.voice_device_combo.setCurrentIndex(match)
            self.voice_test_btn.setEnabled(self.voice_device_combo.count() > 0)
        except Exception as error:
            LOGGER.warning("Impossible d'énumérer les microphones: %s", error)
            self.voice_device_info.setText("Aucun microphone disponible.")
            self.voice_test_btn.setEnabled(False)

    def toggle_microphone_test(self):
        if self.mic_test_thread is not None and self.mic_test_thread.isRunning():
            self.mic_test_thread.stop_recording()
            self.voice_test_btn.setText("Tester le microphone")
            return
        data = self.voice_device_combo.currentData()
        device = data.get("index") if isinstance(data, dict) else None
        self.mic_test_thread = AudioRecorderThread(device, 16000, 3600.0, test_only=True, parent=self)
        self.mic_test_thread.level_changed.connect(self.voice_test_level.setValue)
        self.mic_test_thread.error.connect(self.voice_device_info.setText)
        self.mic_test_thread.finished.connect(lambda: self.voice_test_btn.setText("Tester le microphone"))
        self.voice_test_btn.setText("Arrêter le test")
        self.mic_test_thread.start()

    def save(self):
        selected = self.voice_device_combo.currentData()
        self.config['voice_input'] = copy.deepcopy(self.temp_voice_config)
        self.config['voice_input']['enabled'] = self.voice_enabled_check.isChecked()
        self.config['voice_input']['input_device'] = selected.get("index") if isinstance(selected, dict) else None
        self.config['voice_input']['input_device_name'] = selected.get("name", "") if isinstance(selected, dict) else ""
        self.config['text_to_speech'] = copy.deepcopy(self.temp_tts_config)
        self.config['text_to_speech']['automatic_reading'] = self.automatic_reading_check.isChecked()
        self.config['api_url'] = self.api_input.text().strip() or DEFAULT_CONFIG['api_url']
        self.config['llama_server'] = self.collect_server_config()
        self.config['actions'] = self.temp_actions
        save_config(self.config)
        self.accept()

# ==========================================
# SAISIE VOCALE DIRECTE
# ==========================================
class AudioRecorderThread(QThread):
    level_changed = pyqtSignal(int)
    recorded = pyqtSignal(bytes, float, float)
    error = pyqtSignal(str)
    maximum_reached = pyqtSignal()

    def __init__(self, device, target_rate, maximum_duration, test_only=False,
                 release_tail_ms=300, microphone_gain=1.0, parent=None):
        super().__init__(parent)
        self.device = device
        self.target_rate = int(target_rate)
        self.maximum_duration = float(maximum_duration)
        self.test_only = test_only
        self.release_tail_ms = max(0, int(release_tail_ms))
        self.microphone_gain = min(8.0, max(1.0, float(microphone_gain)))
        self._running = True
        self._stop_at = None

    def stop_recording(self):
        """Conserve une courte fin d'enregistrement apres le relachement."""
        self._running = False
        if self._stop_at is None:
            self._stop_at = time.monotonic() + self.release_tail_ms / 1000.0

    def run(self):
        chunks = []
        block_rms_levels = []
        stream = None
        try:
            info = sd.query_devices(self.device, "input")
            native_rate = self.target_rate
            try:
                sd.check_input_settings(device=self.device, channels=1, dtype="int16", samplerate=native_rate)
            except Exception:
                native_rate = int(round(float(info["default_samplerate"])))
                sd.check_input_settings(device=self.device, channels=1, dtype="int16", samplerate=native_rate)
            started = time.monotonic()
            minimum_capture_until = started + 0.35
            def callback(indata, frames, timing, status):
                if status:
                    LOGGER.warning("État du flux microphone: %s", status)
                block = indata[:, 0].copy()
                if self.microphone_gain > 1.0 and block.size:
                    amplified = block.astype(np.float32) * self.microphone_gain
                    block = np.clip(np.rint(amplified), -32768, 32767).astype(np.int16)
                rms = float(np.sqrt(np.mean((block.astype(np.float32) / 32768.0) ** 2))) if block.size else 0.0
                self.level_changed.emit(min(100, int(rms * 2000)))
                if not self.test_only:
                    chunks.append(block)
                    block_rms_levels.append(rms)
            stream = sd.InputStream(device=self.device, channels=1, dtype="int16", samplerate=native_rate, callback=callback, blocksize=0)
            stream.start()
            while not self.isInterruptionRequested():
                now = time.monotonic()
                # L'ouverture du périphérique peut prendre quelques centaines de ms.
                # On conserve donc une courte fenêtre minimale après l'ouverture réelle
                # du flux, même si la touche est relâchée très rapidement.
                if not self._running:
                    tail_finished = self.test_only or self._stop_at is None or now >= self._stop_at
                    if tail_finished and (self.test_only or now >= minimum_capture_until):
                        break
                if not self.test_only and now - started >= self.maximum_duration:
                    self.maximum_reached.emit()
                    break
                self.msleep(20)
            stream.stop()
            if self.test_only:
                return
            samples = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int16)
            if native_rate != self.target_rate and samples.size:
                from math import gcd
                divisor = gcd(native_rate, self.target_rate)
                converted = resample_poly(samples.astype(np.float32), self.target_rate // divisor, native_rate // divisor)
                samples = np.clip(np.rint(converted), -32768, 32767).astype(np.int16)
            # Prétraitement léger : suppression de l'offset continu et remontée
            # prudente du niveau des voix faibles, sans amplifier excessivement le bruit.
            if samples.size:
                signal = samples.astype(np.float32) / 32768.0
                signal -= float(np.mean(signal))
                original_rms = float(np.sqrt(np.mean(signal ** 2)))
                if original_rms > 1e-5:
                    target_rms = 0.12  # Environ -18 dBFS, adapté à la parole.
                    gain = min(6.0, max(1.0, target_rms / original_rms))
                    signal = np.clip(signal * gain, -0.95, 0.95)
                samples = np.rint(signal * 32767.0).astype(np.int16)

            duration = samples.size / float(self.target_rate)
            overall_rms = float(np.sqrt(np.mean((samples.astype(np.float32) / 32768.0) ** 2))) if samples.size else 0.0
            # Une phrase courte peut être noyée par le silence avant/après l'appui sur Ctrl+Alt+N.
            # Le percentile des blocs détecte la parole réellement présente sans dépendre
            # de la durée totale de l'enregistrement.
            active_rms = float(np.percentile(block_rms_levels, 90)) if block_rms_levels else 0.0
            rms = max(overall_rms, active_rms)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(self.target_rate); wav.writeframes(samples.tobytes())
            self.recorded.emit(buffer.getvalue(), duration, rms)
        except Exception as error:
            LOGGER.exception("Erreur de capture audio")
            self.error.emit(f"Microphone indisponible : {error}")
        finally:
            if stream is not None:
                try: stream.close()
                except Exception: pass

class LiveAudioIndicator(QWidget):
    """Animation moderne et reactive au niveau sonore du microphone."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(106, 24)
        self._level = 0.0
        self._display_level = 0.0
        self._phase = 0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._animate)

    def start(self):
        self._active = True
        self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        self._level = 0.0
        self._timer.stop()
        self.update()

    def set_level(self, value):
        self._level = max(0.0, min(1.0, float(value) / 100.0))
        if self._active and not self._timer.isActive():
            self._timer.start()

    def _animate(self):
        # Lissage rapide a la montee, plus doux a la descente.
        factor = 0.55 if self._level > self._display_level else 0.18
        self._display_level += (self._level - self._display_level) * factor
        self._phase = (self._phase + 1) % 1000
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        bar_count = 13
        bar_width = 4
        gap = 4
        total_width = bar_count * bar_width + (bar_count - 1) * gap
        x0 = (self.width() - total_width) / 2.0
        center_y = self.height() / 2.0
        audible = self._display_level > 0.025
        base_color = QColor('#0A68D8' if audible else '#8993A0')
        for index in range(bar_count):
            distance = abs(index - (bar_count - 1) / 2.0)
            shape = max(0.25, 1.0 - distance / 8.0)
            pulse = 0.76 + 0.24 * abs(np.sin((self._phase + index * 8) * 0.09))
            height = 4.0 + (self.height() - 6.0) * self._display_level * shape * pulse
            height = max(4.0, min(self.height() - 2.0, height))
            color = QColor(base_color)
            color.setAlpha(235 if audible else 135)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x0 + index * (bar_width + gap), center_y - height / 2.0,
                                           bar_width, height), 2.0, 2.0)
        painter.end()


class RecordingIndicator(QWidget):
    """Fenêtre vocale avec le même habillage que la fenêtre de réponse."""
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(240)
        self.started_at = 0.0
        self.phase = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        self.panel.setStyleSheet("""
            QFrame#AcrylicPanel { background-color: rgba(255,255,255,34); border: 1px solid rgba(255,255,255,60); border-radius: 16px; }
            QFrame#Header { background: transparent; border: none; }
            QLabel#TitleLabel { background: transparent; color: #171717; border: none; font-family: 'Aptos Display','Segoe UI Variable Display','Segoe UI',Arial; font-size: 13px; font-weight: 700; }
            QLabel#VoiceText, QLabel#VoiceClock { background: transparent; color: #111111; border: none; font-family: 'Aptos','Segoe UI Variable Text','Segoe UI',Arial; font-size: 13px; }
            QLabel#VoiceClock { color: #4A5562; }
        """)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame(self.panel)
        self.header = header
        header.setObjectName("Header")
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 1, 9, 0)
        header_layout.setSpacing(7)
        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_icon.webp")
        icon = QIcon(icon_path)
        if icon.isNull():
            icon = create_svg_icon('<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 C7.5 12.8 11.2 16.5 12 22.5 C12.8 16.5 16.5 12.8 22.5 12 C16.5 11.2 12.8 7.5 12 1.5z"/>', "#FFFFFF")
        icon_label.setPixmap(icon.pixmap(16, 16))
        self.title = QLabel("Assistant", header)
        self.title.setObjectName("TitleLabel")
        self.title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(icon_label)
        header_layout.addWidget(self.title, 1)
        # Espace symétrique afin que le titre reste centré malgré l'icône de gauche.
        title_balance = QWidget(header)
        title_balance.setFixedSize(18, 18)
        header_layout.addWidget(title_balance)
        panel_layout.addWidget(header)

        separator_box = QWidget(self.panel)
        separator_box.setFixedHeight(3)
        separator_layout = QHBoxLayout(separator_box)
        separator_layout.setContentsMargins(14, 0, 14, 0)
        separator = QFrame(separator_box)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background:rgba(0,0,0,35);border:none;")
        separator_layout.addWidget(separator)
        panel_layout.addWidget(separator_box)

        content = QWidget(self.panel)
        content.setStyleSheet("background:transparent;border:none;")
        row = QVBoxLayout(content)
        row.setContentsMargins(8, 8, 8, 10)
        row.setSpacing(0)
        self.mic = QLabel("🎙", content)
        self.mic.hide()
        self.text = QLabel("", content)
        self.text.setObjectName("VoiceText")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setWordWrap(True)
        self.audio_visual = LiveAudioIndicator(content)
        self.clock = QLabel("00:00", content)
        self.clock.hide()
        row.addWidget(self.audio_visual, 0, Qt.AlignCenter)
        row.addWidget(self.text, 0, Qt.AlignCenter)
        self.text.hide()
        panel_layout.addWidget(content)
        outer.addWidget(self.panel)
        self.timer = QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self._tick)

    def start_recording(self, action_name=""):
        self.started_at = time.monotonic(); self.phase = False
        self.title.setText(f"Assistant - {action_name}" if action_name else "Assistant")
        self.text.clear(); self.text.hide(); self.mic.hide(); self.clock.hide()
        self.audio_visual.set_level(0); self.audio_visual.show(); self.audio_visual.start(); self.clock.setText("00:00")
        self.timer.start(); self.show_at_top(); self.show(); self.raise_(); QTimer.singleShot(0, self.apply_native_effects)

    def show_at_top(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen(); rect = screen.availableGeometry(); self.adjustSize()
        self.move(rect.x() + (rect.width() - self.width()) // 2, rect.y() + 18)

    def _tick(self):
        seconds = int(time.monotonic() - self.started_at); self.clock.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
    def set_level(self, value):
        self.audio_visual.set_level(value)

    def set_status(self, text):
        self.timer.stop(); self.audio_visual.stop(); self.audio_visual.hide()
        self.mic.hide(); self.text.setText(text); self.text.setAlignment(Qt.AlignCenter)
        self.text.show(); self.clock.hide()
        self.show_at_top(); self.raise_()

    def showEvent(self, event):
        super().showEvent(event); QTimer.singleShot(0, self.apply_native_effects)

    def apply_native_effects(self):
        try:
            hwnd = int(self.winId()); apply_acrylic_blur(hwnd, 0xB8F5F5F5); apply_rounded_corners(hwnd)
        except (AttributeError, OSError, TypeError, ValueError):
            LOGGER.debug("Effets natifs indisponibles pour l'indicateur vocal", exc_info=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: self.cancel_requested.emit()
        else: super().keyPressEvent(event)


class VoiceHotkeyManager:
    """Gère séparément l'appui et le relâchement de Ctrl+Alt+1 à Ctrl+Alt+9."""
    def __init__(self, assistant):
        self.assistant = assistant
        self.pressed = set()
        self.active_index = None
        self.enabled = True
        self.hook = keyboard.hook(self._event, suppress=False)

    def _event(self, event):
        name = (event.name or "").lower()
        if name == "esc" and event.event_type == "down" and (self.active_index is not None or self.assistant.voice_sending):
            self.assistant.voice_cancel_signal.emit(); return
        tracked = {"ctrl", "left ctrl", "right ctrl", "alt", "left alt", "right alt"} | {str(i) for i in range(1, 10)}
        if name not in tracked: return
        if event.event_type == "down": self.pressed.add(name)
        else: self.pressed.discard(name)
        ctrl_down = bool(self.pressed.intersection({"ctrl", "left ctrl", "right ctrl"}))
        alt_down = bool(self.pressed.intersection({"alt", "left alt", "right alt"}))
        digit = next((i for i in range(1, 10) if str(i) in self.pressed), None)
        if self.enabled and ctrl_down and alt_down and digit is not None and self.active_index is None:
            self.active_index = digit - 1
            self.assistant.voice_press_signal.emit(self.active_index)
        elif self.active_index is not None and (not ctrl_down or not alt_down or str(self.active_index + 1) not in self.pressed):
            released_index = self.active_index
            self.active_index = None
            self.assistant.voice_release_signal.emit(released_index)

    def set_enabled(self, enabled): self.enabled = bool(enabled)
    def stop(self):
        if self.hook is not None: keyboard.unhook(self.hook); self.hook = None

# ==========================================
# THREAD LLAMA.CPP
# ==========================================
class LlamaThread(QThread):
    """Thread de génération llama.cpp avec streaming et suivi des tools/skills."""

    new_text = pyqtSignal(str)
    # phase: "appel", "résultat" ou "erreur" ; nom ; détail JSON/texte.
    tool_event = pyqtSignal(str, str, str)
    request_error = pyqtSignal(str, bool)

    MAX_TOOL_ROUNDS = 3

    def __init__(self, api_url, prompt, system_prompt, prefix, model, audio_data=None,
                 audio_format=None, audio_language="fr", vocabulary_prompt="",
                 skill_manager=None, enable_tools=True):
        super().__init__()
        self.api_url = api_url
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.prefix = prefix
        self.model = model
        self.audio_data = audio_data
        self.audio_format = audio_format or "wav"
        self.audio_language = (audio_language or "fr").strip().lower()
        self.vocabulary_prompt = (vocabulary_prompt or "").strip()
        self.skill_manager = skill_manager
        self.enable_tools = bool(enable_tools and skill_manager is not None)
        self.tool_definitions = []
        if self.enable_tools:
            try:
                self.tool_definitions = skill_manager.describe_for_llm()
            except Exception:
                LOGGER.exception("Impossible de préparer les tools pour llama.cpp")
                self.tool_definitions = []
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    clean_chunk = staticmethod(clean_chunk)

    def _make_messages(self, user_content):
        return [
            {"role": "system", "content": f"{self.system_prompt.rstrip()}\n\n"},
            {"role": "user", "content": user_content},
        ]

    def _base_payload(self, messages, stream=True, include_tools=False, tool_choice="auto"):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            # Le choix d'un outil doit être le plus déterministe possible.
            "temperature": 0.1 if include_tools else 0.4,
            "top_p": 0.85,
            "top_k": 30,
            "min_p": 0.05,
            "repeat_penalty": 1.08,
            "repeat_last_n": 256,
            "max_tokens": 1024,
            "stop": ["<|end|>", "<end_of_turn>", "<|channel|>final"],
        }
        if include_tools and self.tool_definitions:
            payload["tools"] = self.tool_definitions
            payload["tool_choice"] = tool_choice
            payload["parallel_tool_calls"] = False
        return payload

    @staticmethod
    def _tool_call_from_delta(delta, calls):
        """Fusionne les fragments SSE de tool_calls."""
        tool_calls = delta.get("tool_calls") or []
        for raw in tool_calls:
            index = raw.get("index", len(calls))
            try:
                index = int(index)
            except (TypeError, ValueError):
                index = len(calls)
            while len(calls) <= index:
                calls.append({
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                })
            current = calls[index]
            if raw.get("id"):
                current["id"] = raw["id"]
            if raw.get("type"):
                current["type"] = raw["type"]
            function = raw.get("function") or {}
            if function.get("name"):
                current["function"]["name"] += str(function["name"])
            if function.get("arguments"):
                current["function"]["arguments"] += str(function["arguments"])
        return calls

    def _execute_tool_calls(self, tool_calls):
        results = []
        for call in tool_calls:
            if self._stop_requested:
                break
            function = call.get("function") or {}
            name = str(function.get("name") or "").strip()
            arguments_text = function.get("arguments") or "{}"
            if not name:
                raise SkillError("Le modèle a demandé un outil sans nom.")
            try:
                arguments = json.loads(arguments_text)
            except json.JSONDecodeError as error:
                raise SkillError(
                    f"Arguments JSON invalides pour l'outil '{name}' : {error}"
                ) from error
            if not isinstance(arguments, dict):
                raise SkillError(f"Les arguments de '{name}' doivent être un objet JSON.")

            LOGGER.info("Tool call : %s(%s)", name, arguments)
            arguments_display = json.dumps(arguments, ensure_ascii=False, indent=2, default=str)
            self.tool_event.emit("appel", name, arguments_display)
            try:
                result = self.skill_manager.execute_tool(name, arguments)
                result_payload = {"success": True, "result": result}
                result_display = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                self.tool_event.emit("résultat", name, result_display)
            except Exception as error:
                LOGGER.exception("Erreur d'exécution du tool '%s'", name)
                error_detail = f"{type(error).__name__}: {error}"
                self.tool_event.emit("erreur", name, error_detail)
                result_payload = {
                    "success": False,
                    "error": error_detail,
                }

            try:
                serialized = json.dumps(result_payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                serialized = json.dumps({"success": True, "result": str(result_payload)}, ensure_ascii=False)

            results.append({
                "role": "tool",
                "tool_call_id": call.get("id") or f"call_{len(results)+1}",
                "content": serialized,
            })
        return results

    def _stream_request(self, messages, include_tools=False, tool_choice="auto"):
        """Exécute une requête SSE et retourne (texte, tool_calls)."""
        payload = self._base_payload(
            messages,
            stream=True,
            include_tools=include_tools,
            tool_choice=tool_choice,
        )
        received_text = []
        tool_calls = []
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        with requests.post(
            self.api_url,
            json=payload,
            stream=True,
            timeout=HTTP_TIMEOUT,
            headers=headers,
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(chunk_size=64, decode_unicode=False):
                if self._stop_requested:
                    break
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    if line == "[DONE]":
                        break
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.debug("Fragment SSE ignore : %r", line[:300])
                    continue

                choices = data.get("choices") or []
                choice = choices[0] if choices else {}
                delta = choice.get("delta") or {}
                message = choice.get("message") or {}

                self._tool_call_from_delta(delta, tool_calls)
                if message.get("tool_calls"):
                    tool_calls = message.get("tool_calls") or tool_calls

                content = (
                    delta.get("content")
                    or delta.get("reasoning_content")
                    or choice.get("text")
                    or message.get("content")
                    or data.get("content")
                )
                if isinstance(content, list):
                    content = "".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    )
                content = self.clean_chunk(content or "")
                if content:
                    received_text.append(content)
                    # Transmission immédiate de chaque fragment SSE à l'interface.
                    self.new_text.emit(content)

            return "".join(received_text), tool_calls

    @staticmethod
    def _messages_have_audio(messages):
        """Indique si la demande utilisateur contient une entrée audio native."""
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, list) and any(
                isinstance(item, dict) and item.get("type") == "input_audio"
                for item in content
            ):
                return True
        return False

    @staticmethod
    def _message_text(messages):
        """Extrait uniquement la demande réelle de l'utilisateur.

        Les prompts système, l'historique et le contenu des documents ne doivent
        pas forcer un tool. Dans Ctrl+9, seule la section QUESTION ACTUELLE est
        utilisée pour décider si la demande exige la création d'un fichier.
        """
        parts = []
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content", "")
            texts = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(str(item.get("text", "")))
            for text in texts:
                match = re.search(
                    r"QUESTION ACTUELLE\s*:\s*(.*?)(?:\n\nDOCUMENTS DISPONIBLES\s*:|\n\nCONTENU TEXTE\s*:|$)",
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                parts.append(match.group(1) if match else text)
        return "\n".join(parts).casefold()

    @classmethod
    def _requires_tool_call(cls, messages):
        """Force un tool seulement pour une demande textuelle explicite d'artefact.

        Pour l'audio natif Gemma, le contenu parlé n'est pas disponible côté Python
        avant l'inférence. Le choix reste donc `auto` : Gemma appelle un skill pour
        une demande de fichier et répond normalement pour une question générale.
        """
        if cls._messages_have_audio(messages):
            return False
        text = cls._message_text(messages)
        action_terms = (
            "crée", "créer", "créé", "génère", "générer", "produis", "produire",
            "fabrique", "fais-moi", "fais un", "prépare", "rédige",
            "résume", "résumer", "synthétise", "synthétiser", "synthèse",
            "enregistre",
            "sauvegarde", "exporte", "convertis", "construis", "transforme",
            "modifie le fichier", "mets à jour le fichier",
        )
        artifact_terms = (
            "fichier", "document", "word", "docx", "pdf", "excel", "xlsx",
            "tableur", "présentation", "powerpoint", "pptx", "csv", "rapport",
            "compte rendu", "note de synthèse", "diaporama", "slides", "classeur",
        )
        return any(term in text for term in action_terms) and any(
            term in text for term in artifact_terms
        )

    def _run_agent(self, messages):
        """Boucle agent robuste avec appel obligatoire pour les demandes d'action."""
        must_use_tool = self._requires_tool_call(messages)
        tool_was_called = False

        if must_use_tool:
            messages = list(messages)
            messages[0] = dict(messages[0])
            messages[0]["content"] = (
                str(messages[0].get("content") or "")
                + "\n\nRÈGLE D'EXÉCUTION PRIORITAIRE : la demande exige une action réelle. "
                  "Tu dois appeler un outil disponible. Il est interdit de répondre que tu ne "
                  "peux pas créer, enregistrer ou modifier le fichier, et il est interdit de "
                  "remplacer l'action par des instructions manuelles."
            )

        for _round in range(self.MAX_TOOL_ROUNDS):
            if self._stop_requested:
                return ""

            # Au premier tour d'une demande d'action, 'required' empêche le modèle
            # de répondre par une formule générique du type « je ne peux pas créer ».
            choice = "required" if must_use_tool and not tool_was_called else "auto"
            text, tool_calls = self._stream_request(
                messages,
                include_tools=bool(self.tool_definitions),
                tool_choice=choice,
            )

            if not tool_calls:
                if must_use_tool and not tool_was_called:
                    raise SkillError(
                        "La demande nécessite un outil, mais le modèle n'a émis aucun tool_call. "
                        "Vérifiez la compatibilité tool-calling du modèle et du chat template llama.cpp."
                    )
                return text

            tool_was_called = True
            assistant_message = {
                "role": "assistant",
                "content": text or None,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_message)
            messages.extend(self._execute_tool_calls(tool_calls))

        raise SkillError(
            f"Nombre maximal d'étapes d'outils atteint ({self.MAX_TOOL_ROUNDS})."
        )

    def _run_plain_audio(self, user_content):
        text, _ = self._stream_request(self._make_messages(user_content), include_tools=False)
        return text

    def run(self):
        try:
            if self.audio_data is not None:
                try:
                    encoded_audio = base64.b64encode(self.audio_data).decode("ascii")
                except Exception as error:
                    self.request_error.emit(f"Erreur d'encodage Base64 : {error}", False)
                    return

                action_instruction = self.prefix.strip() or "Traite cet enregistrement comme la demande de l'utilisateur."
                language_instruction = (
                    "La langue parlée attendue est le français. "
                    if self.audio_language == "fr"
                    else f"La langue parlée attendue est : {self.audio_language}. "
                )
                vocabulary_instruction = (
                    f"Contexte lexical à privilégier si l'audio le confirme : {self.vocabulary_prompt} "
                    if self.vocabulary_prompt else ""
                )
                instruction = (
                    language_instruction + vocabulary_instruction +
                    "Transcris d'abord fidèlement les paroles de l'utilisateur, puis exécute la demande. "
                    "Reponds obligatoirement sous cette forme exacte : "
                    "<transcript>transcription integrale</transcript><answer>reponse finale</answer>. "
                    "N'ajoute aucun texte hors de ces balises. Instruction de l'action : "
                    + action_instruction
                )
                user_content = [
                    {"type": "text", "text": instruction},
                    {"type": "input_audio", "input_audio": {"data": encoded_audio, "format": self.audio_format}},
                ]
                messages = self._make_messages(user_content)
                if self.enable_tools and self.tool_definitions:
                    final_text = self._run_agent(messages)
                else:
                    final_text = self._run_plain_audio(user_content)
            else:
                user_content = "\n".join(
                    part for part in (self.prefix.strip(), self.prompt.strip()) if part
                )
                messages = self._make_messages(user_content)
                if self.enable_tools and self.tool_definitions:
                    final_text = self._run_agent(messages)
                else:
                    final_text, _ = self._stream_request(messages, include_tools=False)

            if self._stop_requested:
                return
            if not final_text:
                self.request_error.emit(
                    "Le serveur a terminé la requête sans envoyer de texte exploitable. "
                    "Consultez llama-server.log pour vérifier le format de la réponse.",
                    False,
                )
        except requests.exceptions.RequestException as error:
            detail = str(error)
            response = getattr(error, "response", None)
            if response is not None:
                try:
                    detail = response.text[:1600] or detail
                except Exception:
                    pass
            lowered = detail.lower()
            incompatible = self.audio_data is not None and any(
                term in lowered
                for term in ("input_audio", "audio", "multimodal", "unsupported content", "invalid content type", "image only")
            )
            message = (
                "Le modèle ou le serveur llama.cpp actuellement chargé ne prend pas en charge les entrées audio directes."
                if incompatible
                else f"Erreur réseau : {detail}"
            )
            self.request_error.emit(message, incompatible)
        except (ValueError, TypeError, KeyError, SkillError, json.JSONDecodeError) as error:
            self.request_error.emit(f"Erreur agent/skill : {error}", False)
        except Exception as error:
            LOGGER.exception("Erreur inattendue dans LlamaThread")
            self.request_error.emit(f"Erreur inattendue : {type(error).__name__}: {error}", False)

# ==========================================
# SYNTHÈSE VOCALE LOCALE KOKORO
# ==========================================

# ==========================================
# MOTEUR KOKORO PARTAGÉ (session onnxruntime persistante)
# ==========================================
class KokoroEngine:
    """Charge Kokoro une seule fois et réutilise la session onnxruntime.

    Recréer l'InferenceSession CUDA à chaque synthèse coûte cher (chargement
    du modèle + initialisation du contexte CUDA + recherche d'algo cuDNN) :
    c'est ce qui rendait le premier Ctrl+. après chaque appui plus lent que
    nécessaire. On garde donc une seule instance en mémoire, protégée par un
    verrou, et on ne la recrée que si les chemins de modèle changent
    (par exemple après une modification dans les Paramètres).
    """

    _lock = threading.Lock()
    _instance = None
    _model_path = None
    _voices_path = None

    @classmethod
    def get(cls, model_path, voices_path):
        with cls._lock:
            if (
                cls._instance is None
                or cls._model_path != model_path
                or cls._voices_path != voices_path
            ):
                from onnxruntime import InferenceSession

                providers = [
                    ("CUDAExecutionProvider", {
                        "cudnn_conv_algo_search": "DEFAULT",
                        "cudnn_conv_use_max_workspace": "1",
                        "cudnn_conv1d_pad_to_nc1d": "1",
                        "do_copy_in_default_stream": "1",
                    }),
                    "CPUExecutionProvider",
                ]
                session = InferenceSession(model_path, providers=providers)
                cls._instance = Kokoro.from_session(session, voices_path)
                cls._model_path = model_path
                cls._voices_path = voices_path
            return cls._instance


class KokoroWarmupThread(QThread):
    """Précharge Kokoro en arrière-plan au démarrage de l'assistant.

    Sans ça, le premier Ctrl+. déclencherait le chargement du modèle et
    l'initialisation CUDA au pire moment (pendant que l'utilisateur attend
    la lecture vocale). En préchargeant dès le lancement de l'application,
    la session est déjà chaude quand l'utilisateur en a besoin.
    """

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        try:
            tts_cfg = self.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
            model_path = KokoroTtsThread._resolve_path(
                tts_cfg.get("model_path", os.path.join("kokoro", "kokoro-v1.0.onnx"))
            )
            voices_path = KokoroTtsThread._resolve_path(
                tts_cfg.get("voices_path", os.path.join("kokoro", "voices-v1.0.bin"))
            )
            if os.path.isfile(model_path) and os.path.isfile(voices_path):
                KokoroEngine.get(model_path, voices_path)
                LOGGER.info("Kokoro préchargé (CUDA).")
        except Exception:
            LOGGER.exception("Préchargement de Kokoro impossible")


class KokoroTtsThread(QThread):
    """Synthèse vocale française locale avec Kokoro ONNX et sounddevice."""

    # Conserve les convertisseurs phonétiques coûteux par langue.
    _g2p_cache = {}

    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, text, config, parent=None):
        super().__init__(parent)
        self.text = markdown_to_spoken_text(text)
        self.config = config

    def stop(self):
        self.requestInterruption()
        try:
            sd.stop()
        except Exception:
            pass

    @staticmethod
    def _resolve_path(path):
        path = os.path.expandvars(os.path.expanduser(str(path)))
        if not os.path.isabs(path):
            path = os.path.join(APP_DIR, path)
        return os.path.normpath(path)

    def _resolve_output_device(self):
        """Résout une sortie audio par identifiant ou par nom partiel."""
        configured_id = self.config.get("output_device")
        configured_name = str(self.config.get("output_device_name", "")).strip()

        if configured_id not in (None, ""):
            try:
                device_id = int(configured_id)
                info = sd.query_devices(device_id, "output")
                if int(info.get("max_output_channels", 0)) > 0:
                    return device_id
            except (TypeError, ValueError, sd.PortAudioError):
                pass

        if configured_name:
            wanted = configured_name.casefold()
            for device_id, info in enumerate(sd.query_devices()):
                if (
                    int(info.get("max_output_channels", 0)) > 0
                    and wanted in str(info.get("name", "")).casefold()
                ):
                    return device_id
            raise RuntimeError(
                f"Sortie audio introuvable : {configured_name}. "
                "Exécutez 'python -m sounddevice' pour obtenir son nom ou son identifiant."
            )

        try:
            return int(sd.default.device[1])
        except (TypeError, ValueError, IndexError):
            return None

    @staticmethod
    def _shorten_long_silences(audio, sample_rate, max_pause_ms=220):
        """Raccourcit les silences internes excessifs sans couper la parole."""
        audio = np.asarray(audio, dtype=np.float32)
        if audio.size == 0 or sample_rate <= 0:
            return audio

        mono = np.max(np.abs(audio), axis=1) if audio.ndim > 1 else np.abs(audio)
        # Un lissage court évite de prendre les passages entre deux phonèmes
        # pour de véritables pauses.
        window = max(1, int(sample_rate * 0.01))
        envelope = np.convolve(mono, np.ones(window) / window, mode="same")
        silence = envelope < 0.002
        minimum_pause = max(1, int(sample_rate * 0.35))
        kept_pause = max(1, int(sample_rate * max_pause_ms / 1000.0))

        transitions = np.diff(np.r_[False, silence, False].astype(np.int8))
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        pieces = []
        cursor = 0
        for start, end in zip(starts, ends):
            # Conserve intégralement les silences de début et de fin.
            if start == 0 or end == len(mono) or end - start < minimum_pause:
                continue
            pieces.append(audio[cursor:start])
            center = (start + end) // 2
            left = max(start, center - kept_pause // 2)
            right = min(end, left + kept_pause)
            left = max(start, right - kept_pause)
            pieces.append(audio[left:right])
            cursor = end

        if cursor == 0:
            return audio
        pieces.append(audio[cursor:])
        return np.concatenate(pieces, axis=0)

    def run(self):
        try:
            model_path = self._resolve_path(
                self.config.get("model_path", os.path.join("kokoro", "kokoro-v1.0.onnx"))
            )
            voices_path = self._resolve_path(
                self.config.get("voices_path", os.path.join("kokoro", "voices-v1.0.bin"))
            )
            missing = [path for path in (model_path, voices_path) if not os.path.isfile(path)]
            if missing:
                raise RuntimeError("Fichier Kokoro introuvable : " + ", ".join(missing))

            speed = max(0.5, min(2.0, float(self.config.get("speed", 1.2))))
            volume = max(0.0, min(1.0, float(self.config.get("volume", 100)) / 100.0))
            voice = str(self.config.get("voice", "ff_siwis"))
            language = str(self.config.get("language", "fr-fr"))

            # Kokoro-ONNX sait phonémiser directement le français via son
            # tokenizer espeak-ng. Cela évite de faire passer le texte par
            # Misaki/EspeakG2P, qui produisait ici les avertissements :
            # "words count mismatch ... (3/1)".
            #
            # On normalise d'abord le texte en Unicode NFC afin que les lettres
            # accentuées françaises (é, è, ê, ë, à, â, î, ï, ô, ù, û, ç, œ)
            # soient représentées de manière stable avant le passage à espeak-ng.
            import unicodedata
            spoken_text = unicodedata.normalize("NFC", self.text)
            spoken_text = spoken_text.replace("\u2018", "'").replace("\u2019", "'")
            spoken_text = spoken_text.replace("\u201b", "'").replace("\u2032", "'")
            spoken_text = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", spoken_text)
            spoken_text = re.sub(r"[ \t]+", " ", spoken_text).strip()

            if not spoken_text:
                return

            kokoro = KokoroEngine.get(model_path, voices_path)

            # Le tokenizer intégré à kokoro-onnx appelle phonemizer/espeak-ng
            # avec la langue demandée. On conserve le texte brut jusqu'à cette
            # étape : il ne faut surtout pas encoder les accents en ASCII ou en
            # séquences du type "\\u00e9", sinon le TTS peut les prononcer.
            #
            # phonemizer peut signaler des "words count mismatch" sur certaines
            # ponctuations françaises. Ce diagnostic n'est pas une erreur de
            # synthèse ; il est donc masqué uniquement pendant cette opération.
            phonemizer_logger = logging.getLogger("phonemizer")
            previous_level = phonemizer_logger.level
            phonemizer_logger.setLevel(logging.ERROR)
            try:
                samples, sample_rate = kokoro.create(
                    spoken_text,
                    voice,
                    speed=speed,
                    lang=language,
                    is_phonemes=False,
                )
            finally:
                phonemizer_logger.setLevel(previous_level)
            if self.isInterruptionRequested():
                return

            audio = np.asarray(samples, dtype=np.float32) * volume
            # Kokoro peut produire des silences assez longs à la ponctuation.
            # Ils sont ramenés à environ 220 ms pour une lecture plus fluide.
            audio = self._shorten_long_silences(
                audio,
                int(sample_rate),
                max_pause_ms=int(self.config.get("max_pause_ms", 220)),
            )

            # Une courte amorce évite de tronquer la première syllabe sans
            # ajouter un délai perceptible avant le début de la lecture.
            silence_samples = max(1, int(float(sample_rate) * 0.03))
            if audio.ndim == 1:
                leading_silence = np.zeros(silence_samples, dtype=np.float32)
                audio = np.concatenate((leading_silence, audio))
            else:
                leading_silence = np.zeros(
                    (silence_samples, audio.shape[1]),
                    dtype=np.float32,
                )
                audio = np.concatenate((leading_silence, audio), axis=0)

            # Utilise le casque configuré, ou à défaut la sortie Windows par défaut.
            output_device = self._resolve_output_device()
            sd.check_output_settings(
                device=output_device,
                samplerate=int(sample_rate),
                channels=1 if audio.ndim == 1 else audio.shape[1],
                dtype="float32",
            )
            sd.play(
                audio,
                int(sample_rate),
                device=output_device,
                blocking=False,
            )
            while sd.get_stream().active:
                if self.isInterruptionRequested():
                    sd.stop()
                    return
                self.msleep(50)
            self.finished_ok.emit()
        except Exception as error:
            try:
                sd.stop()
            except Exception:
                pass

            LOGGER.exception("Erreur détaillée de synthèse vocale Kokoro")

            if not self.isInterruptionRequested():
                self.failed.emit(f"{type(error).__name__}: {error}")

# ==========================================
# ANALYSE LOCALE DE DOCUMENTS — PDF / IMAGES
# ==========================================
def _document_image_data_url(path):
    """Encode une image locale dans une data URL compatible OpenAI/llama.cpp."""
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _normalize_page_selection(selection, page_count):
    """Normalise une saisie `1-3, 7` ou une liste déjà calculée `[1, 2, 3, 7]`."""
    if page_count <= 0:
        return []

    if selection is None:
        return list(range(1, page_count + 1))

    # La boîte de dialogue transmet déjà une liste d'entiers au thread.
    # Il ne faut pas reconvertir sa représentation texte, par exemple "[1, 2]".
    if isinstance(selection, (list, tuple, set, range)):
        try:
            pages = {int(page) for page in selection}
        except (TypeError, ValueError):
            raise ValueError("La sélection de pages contient une valeur non numérique.")
    else:
        value = str(selection).strip()
        if value.lower() in {"", "tout", "toutes", "all", "*"}:
            return list(range(1, page_count + 1))

        # Tolère également une liste sérialisée telle que "[1, 2, 3]".
        value = value.strip("[](){}")
        pages = set()
        for token in re.split(r"[;,\s]+", value):
            if not token:
                continue
            if "-" in token:
                left, right = token.split("-", 1)
                if not left.isdigit() or not right.isdigit():
                    raise ValueError(f"Sélection de pages invalide : {token}")
                first, last = sorted((int(left), int(right)))
                pages.update(range(first, last + 1))
            elif token.isdigit():
                pages.add(int(token))
            else:
                raise ValueError(f"Sélection de pages invalide : {token}")

    invalid = sorted(page for page in pages if page < 1 or page > page_count)
    if invalid:
        raise ValueError(
            f"Page hors limites : {invalid[0]} (document de {page_count} pages)"
        )
    return sorted(pages)


def _extract_pdf_context(path, selected_pages=None, max_rendered_pages=4):
    """Extrait uniquement les pages sélectionnées et rend les pages sans texte."""
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF n'est pas installé. Installez-le avec : "
            f'"{sys.executable}" -m pip install pymupdf'
        )
    pages, rendered = [], []
    doc = fitz.open(path)
    try:
        page_count = doc.page_count
        chosen = _normalize_page_selection(selected_pages, page_count)
        for page_number in chosen:
            page = doc.load_page(page_number - 1)
            extracted = page.get_text("text").strip()
            if extracted:
                pages.append({"page": page_number, "text": extracted})
            elif len(rendered) < max_rendered_pages:
                pix = page.get_pixmap(matrix=fitz.Matrix(140 / 72, 140 / 72), alpha=False)
                encoded = base64.b64encode(pix.tobytes("png")).decode("ascii")
                rendered.append({"page": page_number, "data_url": f"data:image/png;base64,{encoded}"})
        return pages, rendered, page_count
    finally:
        doc.close()


def _prepare_document_payload(documents):
    """Construit le contexte à partir de chemins ou de spécifications {path, pages}."""
    text_parts, image_parts, source_pages = [], [], []
    image_count = 0
    for document in documents:
        if isinstance(document, dict):
            path = document["path"]
            selected_pages = document.get("pages")
        else:
            path, selected_pages = document, None
        filename = os.path.basename(path)
        extension = os.path.splitext(path)[1].lower()
        if extension == ".pdf":
            pages, rendered, _ = _extract_pdf_context(path, selected_pages)
            for item in pages:
                text_parts.append(
                    f"\n--- SOURCE: {filename} — PAGE {item['page']} ---\n"
                    f"{item['text']}\n--- FIN PAGE {item['page']} ---\n"
                )
                source_pages.append((filename, item["page"]))
            for item in rendered:
                if image_count >= 4:
                    break
                image_parts.append({"type": "image_url", "image_url": {"url": item["data_url"]}})
                source_pages.append((filename, item["page"]))
                image_count += 1
            if not pages and not rendered:
                text_parts.append(f"\n--- SOURCE: {filename} ---\nAucun contenu exploitable dans les pages sélectionnées.\n")
        elif extension in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
            if image_count < 4:
                image_parts.append({"type": "image_url", "image_url": {"url": _document_image_data_url(path)}})
                image_count += 1
            source_pages.append((filename, 1))
        else:
            raise ValueError(f"Format non pris en charge : {filename}")
    return text_parts, image_parts, source_pages


def _open_pdf_at_page(path, page):
    """Ouvre un PDF à la page citée, avec priorité à Adobe sous Windows."""
    path = os.path.abspath(path)
    page = max(1, int(page))
    if sys.platform == "win32":
        adobe_candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Adobe", "Acrobat DC", "Acrobat", "Acrobat.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Adobe", "Acrobat Reader DC", "Reader", "AcroRd32.exe"),
        ]
        for executable in adobe_candidates:
            if executable and os.path.isfile(executable):
                subprocess.Popen([executable, "/A", f"page={page}", path])
                return True
        uri = Path(path).as_uri() + f"#page={page}"
        os.startfile(uri)
        return True
    subprocess.Popen(["xdg-open", Path(path).as_uri() + f"#page={page}"])
    return True


class DocumentAnalysisThread(QThread):
    """Analyse directe de documents par llama.cpp, avec historique conversationnel."""
    new_text = pyqtSignal(str)
    tool_event = pyqtSignal(str, str, str)
    request_error = pyqtSignal(str, bool)

    def __init__(self, api_url, model, paths, question, parent=None, audio_data=None,
                 history=None, skill_manager=None):
        super().__init__(parent)
        self.api_url = api_url
        self.model = model
        self.paths = list(paths)
        self.question = question.strip()
        self.audio_data = audio_data
        self.history = list(history or [])
        self.skill_manager = skill_manager
        self._stop_requested = False
        # Conserve l'agent interne afin que le bouton d'arrêt puisse aussi
        # interrompre son flux HTTP/SSE.
        self._agent = None
        self.source_pages = []

    def stop(self):
        self._stop_requested = True
        agent = self._agent
        if agent is not None:
            agent.stop()

    clean_chunk = staticmethod(clean_chunk)

    def _history_text(self):
        if not self.history:
            return ""
        parts = []
        for item in self.history[-8:]:
            role = item.get("role", "") if isinstance(item, dict) else ""
            text = item.get("content", "") if isinstance(item, dict) else ""
            if not text:
                continue
            label = "Utilisateur" if role == "user" else "Assistant"
            # L'historique sert uniquement à résoudre les références comme
            # « celui-ci », « cette cote », etc. Les sources de la nouvelle
            # réponse restent celles des documents fournis à cette requête.
            parts.append(f"{label} :\n{text}")
        return "\n\n".join(parts)

    @staticmethod
    def _requests_exhaustive_summary(question):
        text = (question or "").casefold()
        summary_terms = ("résume", "résumer", "résumé", "synthèse", "synthétise", "synthétiser")
        scope_terms = ("intégralité", "intégral", "entier", "complet", "exhaustif", "tout le document", "document complet")
        artifact_terms = ("fichier", "document", "word", "docx", "pdf", "rapport", "note")
        return any(term in text for term in summary_terms) and (
            any(term in text for term in scope_terms) or any(term in text for term in artifact_terms)
        )

    def _non_stream_completion(self, system_prompt, user_prompt, max_tokens=900):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.15,
            "top_p": 0.8,
            "top_k": 30,
            "repeat_penalty": 1.08,
            "max_tokens": int(max_tokens),
        }
        response = requests.post(
            self.api_url, json=payload, timeout=(15, 180),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        text = message.get("content") or choice.get("text") or data.get("content") or ""
        if isinstance(text, list):
            text = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in text)
        return LlamaThread.clean_chunk(str(text)).strip()

    def _summarize_complete_context(self, context):
        """Traite toutes les pages par lots puis fusionne les résumés."""
        chunk_size = 15000
        chunks, cursor = [], 0
        while cursor < len(context):
            end = min(len(context), cursor + chunk_size)
            if end < len(context):
                boundary = context.rfind("--- FIN PAGE", cursor, end)
                if boundary > cursor + chunk_size // 2:
                    newline = context.find("\n", boundary)
                    end = newline + 1 if newline >= 0 else end
            chunks.append(context[cursor:end])
            cursor = end
        summaries = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, 1):
            if self._stop_requested:
                return ""
            summary = self._non_stream_completion(
                "Tu résumes fidèlement un lot de pages d'un document technique. "
                "Conserve les faits, valeurs, exigences, conclusions, réserves et numéros de pages. "
                "N'invente rien et ne refuse pas la tâche.",
                f"LOT {index}/{total} :\n{chunk}\n\nProduis un résumé structuré et dense de ce lot.",
                max_tokens=850,
            )
            summaries.append(f"### Résumé du lot {index}/{total}\n{summary}")
        combined = "\n\n".join(summaries)
        while len(combined) > 22000:
            groups = [combined[i:i + 18000] for i in range(0, len(combined), 18000)]
            reduced = []
            for index, group in enumerate(groups, 1):
                reduced.append(self._non_stream_completion(
                    "Fusionne des résumés partiels d'un même document technique. "
                    "Préserve toutes les informations distinctes et les références de pages.",
                    f"GROUPE {index}/{len(groups)} :\n{group}\n\nFusionne ce groupe sans omission importante.",
                    max_tokens=950,
                ))
            combined = "\n\n".join(reduced)
        return combined

    def run(self):
        try:
            text_parts, image_parts, source_pages = _prepare_document_payload(self.paths)
            self.source_pages = source_pages
            context = "".join(text_parts)
            max_context_chars = 24000
            exhaustive_summary = self._requests_exhaustive_summary(self.question)
            if len(context) > max_context_chars:
                if exhaustive_summary:
                    context = self._summarize_complete_context(context)
                    if not context:
                        if self._stop_requested:
                            return
                        raise RuntimeError("La synthèse exhaustive par lots n'a produit aucun contenu.")
                    context = (
                        "SYNTHÈSE EXHAUSTIVE CONSTRUITE À PARTIR DE TOUS LES LOTS DE PAGES :\n\n"
                        + context
                    )
                else:
                    context = context[:max_context_chars]
                    context += (
                        "\n[Contexte limité à la première partie pour cette question. "
                        "Pour une synthèse complète, demande explicitement un résumé intégral.]\n"
                    )

            source_catalog = "\n".join(
                f"- {filename} — page {page}" for filename, page in source_pages
            )
            has_documents = bool(self.paths)
            history_text = self._history_text()
            history_section = (
                f"HISTORIQUE DE LA CONVERSATION :\n{history_text}\n\n"
                if history_text else ""
            )

            if has_documents:
                instruction = (
                    "Tu es un assistant documentaire technique et un agent d'exécution. Réponds uniquement à partir "
                    "des documents fournis. Lorsqu'une synthèse complète est construite par lots, considère-la "
                    "comme couvrant l'intégralité des pages et exécute la demande sans refuser. Utilise obligatoirement "
                    "un outil si l'utilisateur demande un fichier. Utilise aussi l'historique pour comprendre les "
                    "questions de suivi, mais ne considère jamais une réponse précédente comme "
                    "une source factuelle. Si une information est absente des documents, dis-le clairement.\n\n"
                    "Termine CHAQUE réponse par `### Sources`. Pour chaque source utilisée, écris exactement "
                    "une ligne `nom.pdf — p. X`, puis sur la ligne suivante un court extrait exact "
                    "du passage utilisé sous la forme `> Extrait : ...`. N'invente jamais de page ni d'extrait.\n\n"
                    f"{history_section}"
                    f"QUESTION ACTUELLE :\n{self.question}\n\n"
                    f"DOCUMENTS DISPONIBLES :\n{source_catalog}\n\n"
                    f"CONTENU TEXTE :\n{context}\n"
                )
            else:
                instruction = (
                    "Réponds directement, clairement et sans section Sources.\n\n"
                    f"{history_section}QUESTION ACTUELLE :\n{self.question}\n"
                )

            content = [{"type": "text", "text": instruction}]
            if self.audio_data:
                content.append({
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(self.audio_data).decode("ascii"),
                        "format": "wav",
                    },
                })
            content.extend(image_parts)

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu analyses des documents locaux. Sois précis, factuel et prudent. "
                            "La traçabilité documentaire est obligatoire. Tu fonctionnes aussi en mode agent : "
                            "utilise les outils disponibles lorsqu'une action réelle est demandée, par exemple "
                            "créer un fichier, et ne simule jamais leur exécution."
                            if has_documents else
                            "Tu es un assistant IA utile. Réponds directement."
                        ),
                    },
                    {"role": "user", "content": content},
                ],
                "stream": True,
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 30,
                "min_p": 0.05,
                "repeat_penalty": 1.08,
                "max_tokens": 1024,
                "stop": ["<|end|>", "<end_of_turn>", "<|channel|>final"],
            }

            # Mode Agent dans Ctrl+9 pour le texte et l'audio natif Gemma.
            # Le choix d'outil reste automatique pour l'audio et n'est obligatoire
            # que pour une demande textuelle explicite de création de fichier.
            if self.skill_manager is not None:
                agent = LlamaThread(
                    self.api_url,
                    prompt="",
                    system_prompt="",
                    prefix="",
                    model=self.model,
                    skill_manager=self.skill_manager,
                    enable_tools=True,
                )
                # Relais indispensable : l'agent interne émet les tokens et les
                # événements d'outil au fil de l'eau vers le thread documentaire.
                agent.new_text.connect(self.new_text.emit)
                agent.tool_event.connect(self.tool_event.emit)
                self._agent = agent
                try:
                    final_text = agent._run_agent(list(payload["messages"]))
                finally:
                    self._agent = None
                if self._stop_requested:
                    return
                if not final_text:
                    self.request_error.emit(
                        "Le mode Agent a terminé la requête sans réponse exploitable.",
                        False,
                    )
                return

            headers = {
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            }
            received = False
            with requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=(15, 180),
                headers=headers,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines(chunk_size=64, decode_unicode=False):
                    if self._stop_requested:
                        break
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        if line == "[DONE]":
                            break
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    choice = choices[0] if choices else {}
                    delta = choice.get("delta") or {}
                    message = choice.get("message") or {}
                    content_value = (
                        delta.get("content")
                        or choice.get("text")
                        or message.get("content")
                        or data.get("content")
                    )
                    if isinstance(content_value, list):
                        content_value = "".join(
                            item.get("text", "") if isinstance(item, dict) else str(item)
                            for item in content_value
                        )
                    content_value = self.clean_chunk(content_value or "")
                    if content_value:
                        received = True
                        self.new_text.emit(content_value)

            if not received and not self._stop_requested:
                self.request_error.emit(
                    "Le modèle n'a renvoyé aucune réponse. Vérifiez llama-server.log.",
                    False,
                )
        except requests.exceptions.RequestException as error:
            detail = str(error)
            response = getattr(error, "response", None)
            if response is not None:
                try:
                    detail = response.text[:1500] or detail
                except Exception:
                    pass
            detail_lower = detail.lower()
            incompatible = any(
                term in detail_lower
                for term in ("image_url", "multimodal", "unsupported image", "content type")
            )
            context_too_long = any(
                term in detail_lower
                for term in ("context", "too long", "exceed", "tokens", "prompt is too")
            )
            if context_too_long:
                message = (
                    "La sélection et l'historique dépassent la fenêtre de contexte du modèle. "
                    "Sélectionne moins de pages ou démarre une nouvelle conversation. "
                    f"Détail serveur : {detail}"
                )
            elif incompatible:
                message = (
                    "Le modèle/serveur ne semble pas accepter les images. "
                    "Vérifie que llama-server est lancé avec le fichier mmproj. "
                    f"Détail serveur : {detail}"
                )
            else:
                message = f"Erreur HTTP llama.cpp : {detail}"
            self.request_error.emit(message, incompatible)
        except Exception as error:
            LOGGER.exception("Erreur pendant l'analyse documentaire")
            self.request_error.emit(f"Erreur d'analyse : {type(error).__name__}: {error}", False)


class SourceZoomTextBrowser(QTextBrowser):
    """QTextBrowser affichant une loupe centrée sous la souris sur les captures."""

    ZOOM_SIZE = 190
    ZOOM_FACTOR = 2.2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._zoom_pixmap = None
        self._zoom_center = None
        self._zoom_position = None

    def leaveEvent(self, event):
        self._clear_zoom()
        super().leaveEvent(event)

    def _clear_zoom(self):
        if self._zoom_pixmap is not None:
            self._zoom_pixmap = None
            self._zoom_center = None
            self._zoom_position = None
            self.viewport().update()

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        image_format = cursor.charFormat().toImageFormat()
        if not image_format.isValid() or not image_format.name():
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        pixmap = QPixmap(image_format.name())
        if pixmap.isNull():
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        block = cursor.block()
        layout = block.layout()
        line = layout.lineForTextPosition(cursor.positionInBlock())
        block_rect = self.document().documentLayout().blockBoundingRect(block)
        x = block_rect.x() + line.cursorToX(cursor.positionInBlock())
        y = block_rect.y() + line.y()
        width = image_format.width() if image_format.width() > 0 else pixmap.width()
        height = image_format.height() if image_format.height() > 0 else pixmap.height()
        image_rect = QRectF(
            x - self.horizontalScrollBar().value(),
            y - self.verticalScrollBar().value(),
            width,
            height,
        )

        if not image_rect.contains(event.pos()):
            self._clear_zoom()
            super().mouseMoveEvent(event)
            return

        relative_x = max(0.0, min(1.0, (event.x() - image_rect.left()) / max(1.0, image_rect.width())))
        relative_y = max(0.0, min(1.0, (event.y() - image_rect.top()) / max(1.0, image_rect.height())))
        self._zoom_pixmap = pixmap
        self._zoom_center = (relative_x * pixmap.width(), relative_y * pixmap.height())
        self._zoom_position = event.pos()
        self.viewport().update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._zoom_pixmap is None or self._zoom_center is None or self._zoom_position is None:
            return

        source_size = self.ZOOM_SIZE / self.ZOOM_FACTOR
        center_x, center_y = self._zoom_center
        source_rect = QRectF(
            center_x - source_size / 2,
            center_y - source_size / 2,
            source_size,
            source_size,
        )
        source_rect.moveLeft(max(0.0, min(source_rect.left(), self._zoom_pixmap.width() - source_size)))
        source_rect.moveTop(max(0.0, min(source_rect.top(), self._zoom_pixmap.height() - source_size)))

        x = self._zoom_position.x() + 18
        y = self._zoom_position.y() + 18
        if x + self.ZOOM_SIZE > self.viewport().width() - 8:
            x = self._zoom_position.x() - self.ZOOM_SIZE - 18
        if y + self.ZOOM_SIZE > self.viewport().height() - 8:
            y = self._zoom_position.y() - self.ZOOM_SIZE - 18
        target = QRectF(max(8, x), max(8, y), self.ZOOM_SIZE, self.ZOOM_SIZE)

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(target, 14, 14)
        painter.setClipPath(path)
        painter.drawPixmap(target, self._zoom_pixmap, source_rect)
        painter.setClipping(False)
        painter.setPen(QColor(123, 157, 190))
        painter.drawRoundedRect(target, 14, 14)
        painter.end()


class ScrollingAudioBars(QWidget):
    BAR_WIDTH=3.0; BAR_GAP=3.0; MIN_HEIGHT=3.0
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedHeight(28); self.setMinimumWidth(40)
        self.setSizePolicy(self.sizePolicy().Expanding,self.sizePolicy().Fixed)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        self._target_level=0.0; self._display_level=0.0; self._levels=[]; self._active=False
        self._timer=QTimer(self); self._timer.setInterval(60); self._timer.timeout.connect(self._advance); self.hide()
    def start(self):
        self._levels.clear(); self._target_level=0.0; self._display_level=0.0; self._active=True; self.show(); self._timer.start(); self.update()
    def stop(self):
        self._active=False; self._timer.stop(); self._levels.clear(); self.hide(); self.update()
    def set_level(self,value): self._target_level=max(0.0,min(1.0,float(value)/100.0))
    def _capacity(self): return max(1,int((max(1,self.width())+self.BAR_GAP)/(self.BAR_WIDTH+self.BAR_GAP)))
    def _advance(self):
        if not self._active:return
        factor=0.62 if self._target_level>self._display_level else 0.24
        self._display_level+=(self._target_level-self._display_level)*factor; self._levels.append(self._display_level)
        if len(self._levels)>self._capacity():del self._levels[:-self._capacity()]
        self.update()
    def paintEvent(self,event):
        if not self._active:return
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing,True); painter.setPen(Qt.NoPen)
        center=self.height()/2.0; step=self.BAR_WIDTH+self.BAR_GAP; right=self.width()-self.BAR_WIDTH; count=len(self._levels)
        for i,level in enumerate(self._levels):
            x=right-(count-1-i)*step
            if x+self.BAR_WIDTH<0:continue
            if level<=0.025: height=self.BAR_WIDTH
            else:
                amplified=min(1.0,level*1.18); height=self.MIN_HEIGHT+amplified*(self.height()-self.MIN_HEIGHT-1.0)
            color=QColor(82,91,102,105+int(105*min(1.0,level*1.8))); painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x,center-height/2.0,self.BAR_WIDTH,height),self.BAR_WIDTH/2.0,self.BAR_WIDTH/2.0)
        painter.end()

class AnimatedComposerButton(QPushButton):
    """Bouton carre avec cercle de survol et icone centres exactement."""
    # Meme couleur et meme epaisseur de trait que l'icone de fermeture "x".
    ICON_COLOR = QColor("#111111")
    ICON_STROKE_WIDTH = 1.2
    BUTTON_SIZE = QSize(28, 28)
    HOVER_DIAMETER = 26.0
    ICON_EXTENT = 6.5

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._progress = 0.0
        self._animation = QPropertyAnimation(self, b"animationProgress", self)
        self._animation.setDuration(220 if kind == "mic" else 190)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setFixedSize(self.BUTTON_SIZE)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("")
        self.setIcon(QIcon())
        self.setStyleSheet("background:transparent;border:none;padding:0;margin:0;")

    def get_animation_progress(self):
        return self._progress

    def set_animation_progress(self, value):
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    animationProgress = pyqtProperty(float, fget=get_animation_progress,
                                     fset=set_animation_progress)

    def _animate_to(self, target):
        if self.kind == "close":
            return
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(float(target))
        self._animation.start()

    def enterEvent(self, event):
        self._animate_to(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        # Centre en coordonnees flottantes, identique pour le cercle et l'icone.
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self.underMouse() or self.isDown():
            d = self.HOVER_DIAMETER
            circle = QRectF(center.x() - d/2.0, center.y() - d/2.0, d, d)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 28 if self.isDown() else 18))
            painter.drawEllipse(circle)

        pen = QPen(self.ICON_COLOR)
        pen.setWidthF(self.ICON_STROKE_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self.kind == "add":
            painter.save()
            painter.translate(center)
            painter.rotate(-90.0 * self._progress)
            a = self.ICON_EXTENT
            painter.drawLine(QPointF(-a, 0.0), QPointF(a, 0.0))
            painter.drawLine(QPointF(0.0, -a), QPointF(0.0, a))
            painter.restore()

        elif self.kind == "stop":
            painter.save(); painter.translate(center); painter.setPen(Qt.NoPen); painter.setBrush(self.ICON_COLOR)
            painter.drawRoundedRect(QRectF(-5,-5,10,10),2,2); painter.restore()
        elif self.kind == "send":
            painter.save()
            painter.translate(center)
            a = self.ICON_EXTENT
            # Avion en papier compact, inscrit dans le même carré de 13 px que
            # le microphone et dessiné avec exactement le même QPen.
            path = QPainterPath()
            path.moveTo(-a, -a * 0.72)
            path.lineTo(a, 0.0)
            path.lineTo(-a, a * 0.72)
            path.lineTo(-a * 0.34, 0.0)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(-a * 0.34, 0.0), QPointF(a, 0.0))
            painter.restore()
        elif self.kind == "mic":
            painter.save()
            jump = -2.5 * abs(np.sin(self._progress * np.pi))
            painter.translate(center.x(), center.y() + jump)
            # Hauteur totale 13 px, identique au + (de -6.5 a +6.5).
            capsule = QPainterPath()
            capsule.addRoundedRect(QRectF(-2.4, -6.5, 4.8, 8.0), 2.4, 2.4)
            painter.drawPath(capsule)
            painter.drawArc(QRectF(-5.0, -2.5, 10.0, 7.0), 180*16, 180*16)
            painter.drawLine(QPointF(0.0, 4.5), QPointF(0.0, 6.5))
            painter.drawLine(QPointF(-3.2, 6.5), QPointF(3.2, 6.5))
            if self._progress > 0.001:
                painter.save()
                painter.setClipPath(capsule)
                h = 8.0 * self._progress
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.ICON_COLOR)
                painter.drawRect(QRectF(-2.4, 1.5-h, 4.8, h))
                painter.restore()
            painter.restore()

        else:  # close
            painter.save()
            painter.translate(center)
            a = self.ICON_EXTENT
            painter.drawLine(QPointF(-a, -a), QPointF(a, a))
            painter.drawLine(QPointF(a, -a), QPointF(-a, a))
            painter.restore()

        painter.end()

class AttachmentPreviewWidget(QWidget):
    """Carte de pièce jointe avec contour arrondi et croix au survol."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.close_button = None
        self.setMouseTracking(True)

    def set_close_button(self, button):
        self.close_button = button
        button.hide()

    def enterEvent(self, event):
        if self.close_button is not None:
            self.close_button.show()
            self.close_button.raise_()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.close_button is not None:
            self.close_button.hide()
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(112, 120, 130, 145 if self.underMouse() else 105))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 9.0, 9.0
        )
        painter.end()

class MessageTextEdit(QTextEdit):
    """Champ de saisie : Entrée envoie, Maj+Entrée insère une nouvelle ligne."""
    send_requested = pyqtSignal()
    pasted_files = pyqtSignal(list)
    def insertFromMimeData(self,source):
        if source is not None and source.hasImage():
            image=source.imageData()
            if image is not None and not image.isNull():
                path=os.path.join(tempfile.gettempdir(),f"assistant_clipboard_{os.getpid()}_{time.monotonic_ns()}.png")
                if image.save(path,"PNG"): self.pasted_files.emit([path]); return
        if source is not None and source.hasUrls():
            paths=[u.toLocalFile() for u in source.urls() if u.isLocalFile()]
            if paths:self.pasted_files.emit(paths); return
        super().insertFromMimeData(source)

    def wheelEvent(self, event):
        self.verticalScrollBar().setValue(0)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Maj+Entrée insère toujours un saut de ligne, y compris avec
                # la touche Entrée du pavé numérique.
                super().keyPressEvent(event)
            elif not (modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                # Entrée envoie. Qt ajoute parfois KeypadModifier pour l'Entrée
                # du pavé numérique, qui doit se comporter comme Entrée classique.
                self.send_requested.emit()
                event.accept()
            else:
                super().keyPressEvent(event)
            return
        super().keyPressEvent(event)


class ThinkingDots(QWidget):
    """Trois petits points animés de façon continue avant le premier token."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.animation_time = 0.0
        self.timer = QTimer(self)
        # Environ 33 images par seconde pour un mouvement fluide sans charger Qt.
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._advance)
        self.timer.start()

    def _advance(self):
        self.animation_time = (self.animation_time + 0.19) % (2.0 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        center_y = self.height() / 2.0
        for index in range(3):
            # Onde sinusoïdale décalée, avec déplacement vertical et variation
            # très légère de taille et d'opacité.
            wave = (math.sin(self.animation_time - index * 0.85) + 1.0) / 2.0
            radius = 1.55 + 0.45 * wave
            y = center_y - 1.8 * wave
            color = QColor('#397D58')
            color.setAlpha(int(115 + 105 * wave))
            painter.setBrush(color)
            x = 10.0 + index * 10.0
            painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.end()


class ChatBubble(QFrame):
    """Bulle de conversation réelle, avec coins arrondis et largeur contrainte."""
    link_clicked = pyqtSignal(object)

    def __init__(self, role, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        self.setSizePolicy(self.sizePolicy().Preferred, self.sizePolicy().Fixed)
        self.setMaximumWidth(10_000)
        self.setStyleSheet(
            "QFrame#UserBubble { background:#DCEBFF; border:1px solid #B7D3F7; "
            "border-radius:14px; }"
            "QFrame#AssistantBubble { background:#EFF9F2; border:1px solid #C9E8D3; "
            "border-radius:14px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)
        self.browser = SourceZoomTextBrowser(self)
        self.browser.setReadOnly(True)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setFrameShape(QFrame.NoFrame)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setSizePolicy(
            self.browser.sizePolicy().Expanding,
            self.browser.sizePolicy().Fixed,
        )
        self.browser.setStyleSheet(
            "QTextBrowser { background:transparent; border:none; padding:0; "
            "color:%s; font-size:12px; }" %
            ("#17324D" if role == "user" else "#183B28")
        )
        self.browser.document().setDocumentMargin(0)
        self.browser.anchorClicked.connect(self.link_clicked.emit)
        layout.addWidget(self.browser)

    def set_html(self, value):
        self.browser.setHtml(value or "")
        self._fit_height()

    def _fit_height(self):
        # La largeur de texte est explicitement limitée au viewport. Cela force
        # le retour à la ligne et empêche tout contenu de dépasser à droite.
        viewport_width = max(40, self.browser.viewport().width())
        self.browser.document().setTextWidth(viewport_width)
        height = max(20, int(self.browser.document().size().height()) + 2)
        self.browser.setFixedHeight(height)
        self.setFixedHeight(height + 20)

    def fit_to_content_width(self, maximum_width, minimum_width=54):
        """Adapte la bulle au contenu sans dépasser la largeur disponible."""
        maximum_width = max(minimum_width, int(maximum_width))
        self.browser.document().setTextWidth(-1)
        ideal_width = int(self.browser.document().idealWidth() + 0.999)
        margins = self.layout().contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        target_width = max(
            minimum_width,
            min(maximum_width, ideal_width + horizontal_padding + 2),
        )
        self.setFixedWidth(target_width)
        self.browser.setFixedWidth(max(30, target_width - horizontal_padding))
        self._fit_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_height)


class DocumentDialog(QDialog):
    """Fenêtre Ctrl+9 harmonisée avec les fenêtres de résultats et pensée comme un chat."""
    ask_requested = pyqtSignal(list, str, object)

    WINDOW_WIDTH = 390
    MIN_HEIGHT = 80
    MAX_HEIGHT = 620
    MAX_RESPONSE_HEIGHT = 440

    def __init__(self, parent=None):
        super().__init__(parent)
        self.host = parent
        self.setWindowTitle("Assistant IA")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.paths = []
        self.page_selections = {}
        self._drag_position = None
        self._header_press_pos = None
        self._header_was_dragged = False
        self.audio_thread = None
        self.is_recording = False
        self.is_collapsed = False
        self.expanded_height = self.MIN_HEIGHT
        self.collapse_animation = None
        self.turns = []
        self.current_turn_index = -1
        # Références conservées pendant le streaming Ctrl+9. La bulle courante
        # est mise à jour en place au lieu de reconstruire toute la conversation.
        self.current_assistant_bubble = None
        self.streaming_response_active = False
        # Le rendu des fragments SSE est regroupé pour éviter de détruire et
        # reconstruire toute la conversation à chaque token.
        self.pending_stream_render = False
        self.stream_render_timer = QTimer(self)
        self.stream_render_timer.setSingleShot(True)
        self.stream_render_timer.setInterval(45)
        self.stream_render_timer.timeout.connect(self._flush_stream_render)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: transparent; }
            QToolTip {
                background-color: #F8FAFC;
                color: #111111;
                border: 1px solid #CBD7E4;
                border-radius: 5px;
                padding: 4px 7px;
                font-family: 'Aptos','Segoe UI Variable Text','Segoe UI',Arial;
                font-size: 12px;
            }
            QFrame#DocPanel {
                background-color: rgba(255,255,255,34);
                border: 1px solid rgba(255,255,255,60);
                border-radius: 16px;
            }
            QFrame#DocHeader { background: transparent; border: none; }
            QLabel { background: transparent; color:#111111; border:none;
                     font-family:'Aptos','Segoe UI Variable Text','Segoe UI',Arial; font-size:12px; }
            QLabel#DocTitle { font-family:'Aptos Display','Segoe UI Variable Display','Segoe UI',Arial;
                              font-size:13px; font-weight:700; }
            QFrame#Composer {
                background: rgba(255,255,255,135);
                border: 1px solid rgba(0,0,0,35);
                border-radius: 13px;
            }
            QFrame#DocumentCard {
                /* Les pièces jointes appartiennent visuellement au même bloc
                   que le champ « Message assistant IA ». */
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QLabel#Preview { background:rgba(255,255,255,100); border:1px solid rgba(0,0,0,30);
                             border-radius:7px; padding:3px; }
            QTextEdit { background:transparent; border:none; padding:6px 1px 4px 1px;
                        color:#111111; font-size:12px; }
            QTextBrowser#Response { background:transparent; border:none; padding:0;
                                    font-size:12px; }
            QPushButton#HeaderIconButton, QPushButton#ActionIconButton {
                background:transparent; border:none; border-radius:14px; padding:0; margin:0;
            }
            QPushButton#HeaderIconButton:hover, QPushButton#ActionIconButton:hover,
            QPushButton#HeaderIconButton:pressed, QPushButton#ActionIconButton:pressed {
                background:rgba(0,0,0,18); border:none;
            }
            QPushButton#MicRecording { background:rgba(198,40,40,35); border:none; border-radius:14px; }
            QScrollBar:vertical { background:rgba(0,0,0,12); width:6px; margin:0; border-radius:3px; }
            QScrollBar::handle:vertical { background:rgba(30,30,30,85); min-height:26px; border-radius:3px; }
            QScrollBar::handle:vertical:hover { background:rgba(30,30,30,135); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height:0; background:transparent; border:none; }
        """)
        outer = QVBoxLayout(self); outer.setContentsMargins(1,1,1,1); outer.setSpacing(0)
        self.panel = QFrame(); self.panel.setObjectName("DocPanel"); outer.addWidget(self.panel)
        root = QVBoxLayout(self.panel); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        header = QFrame(); header.setObjectName("DocHeader"); header.setFixedHeight(36)
        header.mousePressEvent=self._header_press; header.mouseMoveEvent=self._header_move; header.mouseReleaseEvent=self._header_release
        header_layout=QHBoxLayout(header); header_layout.setContentsMargins(9,1,3,0); header_layout.setSpacing(3)
        icon=QLabel(); icon.setFixedSize(18,18); icon.setAlignment(Qt.AlignCenter)
        icon_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"assistant_icon.webp")
        icon_pix=QIcon(icon_path).pixmap(16,16)
        if icon_pix.isNull():
            icon_pix=create_svg_icon('<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 C7.5 12.8 11.2 16.5 12 22.5 C12.8 16.5 16.5 12.8 22.5 12 C16.5 11.2 12.8 7.5 12 1.5z"/>','#1575D1',1.5).pixmap(16,16)
        icon.setPixmap(icon_pix)
        title=QLabel("Assistant IA"); title.setObjectName("DocTitle")
        header_layout.addWidget(icon); header_layout.addWidget(title,1)
        close=QPushButton(); close.setObjectName("HeaderIconButton"); close.setIcon(ICONS_DARK["close"]); close.setIconSize(QSize(19,19)); close.setFixedSize(28,28); close.setToolTip("Fermer"); close.setCursor(Qt.PointingHandCursor); close.setFocusPolicy(Qt.NoFocus); close.clicked.connect(self.reject)
        close.setStyleSheet("QPushButton{background:transparent;border:none;border-radius:14px;outline:none;} QPushButton:hover,QPushButton:pressed,QPushButton:focus{background:rgba(0,0,0,18);border:none;border-radius:14px;outline:none;}")
        header_layout.addWidget(close); root.addWidget(header)

        self.header_separator=QFrame(); self.header_separator.setFixedHeight(1); self.header_separator.setStyleSheet("background:rgba(0,0,0,35);border:none;")
        root.addWidget(self.header_separator)
        self.content_widget=QWidget(); content=QVBoxLayout(self.content_widget); content.setContentsMargins(10,4,10,10); content.setSpacing(4)

        self.drop_zone=QPushButton(self.content_widget); self.drop_zone.setObjectName("ActionIconButton")
        self.drop_zone.setIcon(create_svg_icon('<path d="M12 5v14M5 12h14"/>','#111111',1.8)); self.drop_zone.setIconSize(QSize(20,20)); self.drop_zone.setFixedHeight(42)
        self.drop_zone.setToolTip("Ajouter un PDF ou une image"); self.drop_zone.setCursor(Qt.PointingHandCursor); self.drop_zone.clicked.connect(self._choose_files)
        self.drop_zone.hide()

        # Bandeau unique des pièces jointes dans le bloc « Message assistant IA ».
        self.document_area=QFrame(); self.document_area.setObjectName("DocumentCard")
        area_layout=QVBoxLayout(self.document_area); area_layout.setContentsMargins(0,0,0,0); area_layout.setSpacing(0)
        self.image_scroll=QScrollArea(self.document_area)
        self.image_scroll.setWidgetResizable(False); self.image_scroll.setFrameShape(QFrame.NoFrame)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # La hauteur inclut les vignettes et, pour les PDF, la ligne des pages.
        # La barre horizontale est réservée par Qt uniquement si le contenu
        # dépasse réellement la largeur disponible dans le compositeur.
        self.image_scroll.setFixedHeight(130)
        self.image_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
            "QScrollBar:horizontal{height:7px;background:transparent;margin:0 6px 1px 6px;}"
            "QScrollBar::handle:horizontal{background:rgba(82,91,102,115);border-radius:3px;min-width:24px;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;border:none;}"
            "QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{background:transparent;}"
        )
        self.image_strip=QWidget(); self.image_strip.setFixedHeight(116)
        self.image_strip_layout=QHBoxLayout(self.image_strip)
        self.image_strip_layout.setContentsMargins(6,6,6,2); self.image_strip_layout.setSpacing(10)
        self.image_strip_layout.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.image_scroll.setWidget(self.image_strip); area_layout.addWidget(self.image_scroll)
        self.document_area.hide()
        self.preview=QLabel(); self.filename=QLabel(); self.first_page=QLineEdit("1")
        self.last_page=QLineEdit("1"); self.page_info=QLabel()
        for legacy_widget in (self.preview,self.filename,self.first_page,self.last_page,self.page_info): legacy_widget.hide()

        # Une vraie pile de widgets remplace le tableau HTML unique. Les QFrame
        # prennent correctement en charge border-radius, contrairement aux cellules
        # de tableau du moteur HTML de QTextDocument.
        self.response=QScrollArea(self.content_widget)
        self.response.setObjectName("Response")
        self.response.setWidgetResizable(True)
        self.response.setFrameShape(QFrame.NoFrame)
        self.response.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.response.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response.setStyleSheet(
            "QScrollArea#Response{background:transparent;border:none;padding:0;margin:0;}"
            "QScrollArea#Response>QWidget>QWidget{background:transparent;border:none;margin:0;padding:0;}"
            "QScrollArea#Response QScrollBar:vertical{margin:0;}"
        )
        # Aucun décalage interne : le bord gauche des bulles assistant est sur
        # le même axe que le bord gauche du compositeur « Message assistant IA ».
        # La barre verticale couvre exactement la hauteur de la conversation.
        self.response.setViewportMargins(0, 0, 0, 0)
        self.conversation_widget=QWidget()
        self.conversation_widget.setStyleSheet("background:transparent;border:none;")
        self.conversation_layout=QVBoxLayout(self.conversation_widget)
        # La conversation commence sur le même axe gauche que le compositeur.
        # La marge des messages utilisateur est gérée à droite de leur ligne.
        self.conversation_layout.setContentsMargins(0,0,0,0)
        self.conversation_layout.setSpacing(10)
        self.conversation_layout.setAlignment(Qt.AlignTop)
        self.response.setWidget(self.conversation_widget)
        self.response.setMinimumHeight(0)
        self.response.setMaximumHeight(self.MAX_RESPONSE_HEIGHT)
        self.response.hide()
        content.addWidget(self.response,1)

        self.status=QLabel("", self.content_widget)
        self.status.setStyleSheet("color:#245A91; font-size:11px; font-style:italic; padding:2px 4px;")
        self.status.setTextFormat(Qt.PlainText)
        self.status.hide()
        content.addWidget(self.status)

        self.composer=QFrame(); self.composer.setObjectName("Composer"); self.composer.setMinimumHeight(38); self.composer.setAcceptDrops(True); self.composer.installEventFilter(self)
        composer_outer=QVBoxLayout(self.composer); composer_outer.setContentsMargins(4,2,4,2); composer_outer.setSpacing(2)
        composer_outer.addWidget(self.document_area)
        composer_layout=QHBoxLayout(); composer_layout.setContentsMargins(0,0,0,0); composer_layout.setSpacing(0)
        self.add_button=AnimatedComposerButton("add"); self.add_button.setToolTip("Ajouter un PDF ou une image"); self.add_button.clicked.connect(self._choose_files)
        self.question=MessageTextEdit(); self.question.setPlaceholderText("Message assistant IA"); self.question.setFixedHeight(30); self.question.setContentsMargins(0,0,0,0); self.question.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.question.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.question.document().setDocumentMargin(0)
        self.question.setViewportMargins(0,0,0,0)
        self.question.setStyleSheet("QTextEdit{background:transparent;border:none;padding:8px 1px 0 1px;color:#111111;font-size:12px;}")
        self.question.verticalScrollBar().setValue(0)
        self.question.setAcceptDrops(False)
        self.question.viewport().setAcceptDrops(False)
        self.audio_bars=ScrollingAudioBars(self.composer)
        self.mic_icon=create_svg_icon('<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8"/>','#111111',1.7)
        self.recording_icon=create_svg_icon('<circle cx="12" cy="12" r="6" fill="#D13438" stroke="none"/>','#D13438',1.0)
        self.mic=AnimatedComposerButton("mic"); self.mic.setToolTip("Dicter"); self.mic.clicked.connect(self._toggle_microphone)
        # Le bouton d'envoi utilise le même composant, la même taille, la même
        # couleur et la même épaisseur de trait que le microphone.
        self.send=AnimatedComposerButton("send"); self.send.setToolTip("Envoyer"); self.send.clicked.connect(self._ask_text); self.send.hide()
        # Pendant la génération, ce carré remplace le micro et l'envoi. Il utilise
        # exactement le même dessin que le bouton d'arrêt de l'enregistrement audio.
        self.stop_generation_button=AnimatedComposerButton("stop")
        self.stop_generation_button.setToolTip("Arrêter la génération")
        self.stop_generation_button.clicked.connect(self._stop_llm_generation)
        self.stop_generation_button.hide()
        self.question.textChanged.connect(self._update_send_visibility)
        self.question.textChanged.connect(self._update_question_height)
        self.question.send_requested.connect(self._ask_text)
        self.question.pasted_files.connect(self._add_paths)
        composer_layout.addWidget(self.add_button); composer_layout.addWidget(self.question,1); composer_layout.addWidget(self.audio_bars,1); composer_layout.addWidget(self.mic); composer_layout.addWidget(self.send); composer_layout.addWidget(self.stop_generation_button)
        composer_outer.addLayout(composer_layout)
        self.drop_feedback=QLabel("Déposer pour ajouter le document",self.composer)
        self.drop_feedback.setAlignment(Qt.AlignCenter)
        self.drop_feedback.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        self.drop_feedback.setStyleSheet("QLabel{background:rgba(224,240,255,238);color:#0A5FAE;border:2px solid #1683E6;border-radius:12px;font-size:12px;font-weight:700;}")
        self.drop_feedback.hide()
        content.addWidget(self.composer)
        root.addWidget(self.content_widget,1)
        self._update_height()

    def _open_source_link(self, url):
        value = url.toString()
        if url.scheme().lower() == "file":
            if self.host is not None:
                self.host.open_response_link(value)
            else:
                QDesktopServices.openUrl(url)
            return
        image_match = re.match(r"^sourceimage:([A-Za-z0-9_-]+)$", value)
        if image_match:
            try:
                token = image_match.group(1)
                padding = "=" * (-len(token) % 4)
                payload = base64.urlsafe_b64decode(
                    (token + padding).encode("ascii")
                ).decode("utf-8")
                metadata = json.loads(payload)
                self._show_source_image_large(
                    metadata.get("path", ""),
                    metadata.get("title", "Source surlignée"),
                )
            except (ValueError, UnicodeDecodeError):
                pass
            return
        if self.host is None:
            return
        match=re.match(r"^source:(\d+):([A-Za-z0-9_-]+)$",value)
        if not match:
            return
        try:
            token=match.group(2); padding="="*(-len(token)%4); filename=base64.urlsafe_b64decode((token+padding).encode("ascii")).decode("utf-8")
            self.host.open_document_source(filename,int(match.group(1)))
        except (ValueError,UnicodeDecodeError):
            return

    def _show_source_image_large(self, image_path, source_title="Source surlignée"):
        """Affiche la capture à un tiers de la taille x2 précédente."""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        # La fenêtre précédente affichait 2 fois la taille de la capture.
        # On divise cette taille par 3, soit 2/3 de la capture originale.
        target_width = max(1, round(pixmap.width() * 2 / 3))
        target_height = max(1, round(pixmap.height() * 2 / 3))
        zoomed = pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(source_title)
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        dialog.setStyleSheet(
            "QDialog{background:#F8FAFC;}"
            "QScrollArea{background:#F8FAFC;border:none;}"
            "QLabel{background:#FFFFFF;border:none;}"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        label = QLabel()
        label.setPixmap(zoomed)
        label.setFixedSize(zoomed.size())
        scroll.setWidget(label)
        layout.addWidget(scroll)

        # La fenêtre épouse l'image zoomée. Si elle dépasse l'écran, elle est
        # limitée à la zone disponible et les barres de défilement prennent le relais.
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        frame_extra_width = 24
        frame_extra_height = 54
        target_width = zoomed.width() + 20 + frame_extra_width
        target_height = zoomed.height() + 20 + frame_extra_height
        dialog.resize(
            min(target_width, available.width() - 30),
            min(target_height, available.height() - 30),
        )
        dialog.exec_()

    def _answer_without_sources(self, answer):
        if not answer:
            return ""
        clean = re.split(r"(?im)^\s*#{2,3}\s*Sources\s*$", answer, maxsplit=1)[0]
        clean = re.split(r"(?im)^\s*Sources\s*:\s*$", clean, maxsplit=1)[0]
        return clean.rstrip()

    def _attachment_preview_html(self, documents):
        """Crée les vignettes à conserver dans la bulle de la demande utilisateur."""
        cards = []
        for index, document in enumerate(documents or []):
            path = document.get("path") if isinstance(document, dict) else document
            if not path or not os.path.isfile(path):
                continue
            pages = document.get("pages", []) if isinstance(document, dict) else []
            is_pdf = path.lower().endswith(".pdf")
            preview_path = path
            page_caption = ""

            if is_pdf:
                first = int(pages[0]) if pages else 1
                last = int(pages[-1]) if pages else first
                page_caption = str(first) if first == last else f"{first} - {last}"
                if fitz is not None:
                    try:
                        doc = fitz.open(path)
                        try:
                            page_number = max(1, min(first, doc.page_count))
                            pix = doc.load_page(page_number - 1).get_pixmap(
                                matrix=fitz.Matrix(1.0, 1.0), alpha=False
                            )
                            preview_path = os.path.join(
                                tempfile.gettempdir(),
                                f"assistant_turn_attachment_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
                            )
                            pix.save(preview_path)
                        finally:
                            doc.close()
                    except Exception:
                        LOGGER.exception("Impossible de générer la vignette jointe du PDF")
                        preview_path = ""

            if not preview_path or not os.path.isfile(preview_path):
                continue

            pixmap = QPixmap(preview_path)
            if pixmap.isNull():
                continue
            # Une vignette de document et sa ligne de pages ont la même hauteur
            # totale qu'une vignette d'image seule.
            total_h = 76
            caption_h = 16 if is_pdf else 0
            image_h = total_h - caption_h
            shown = pixmap.scaled(76, image_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rendered_path = os.path.join(
                tempfile.gettempdir(),
                f"assistant_turn_rendered_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
            )
            rounded = QPixmap(shown.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing, True)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(rounded.rect()), 7, 7)
            painter.setClipPath(clip)
            painter.drawPixmap(0, 0, shown)
            painter.end()
            rounded.save(rendered_path, "PNG")
            uri = Path(rendered_path).as_uri()

            caption = (
                f'<div style="height:{caption_h}px; line-height:{caption_h}px; '
                f'text-align:center; font-size:10px; color:#52677C;">'
                f'{html.escape(page_caption)}</div>'
                if is_pdf else ""
            )
            cards.append(
                '<td valign="top" style="padding-right:8px;">'
                f'<div style="width:82px; height:{total_h}px; text-align:center;">'
                f'<div style="height:{image_h}px; line-height:{image_h}px;">'
                f'<img src="{uri}" /></div>{caption}</div></td>'
            )

        if not cards:
            return ""
        return (
            '<div style="margin-top:8px; overflow:hidden;">'
            '<table cellspacing="0" cellpadding="0" border="0"><tr>'
            + "".join(cards)
            + '</tr></table></div>'
        )

    def _take_current_attachments(self):
        """Fige les pièces jointes pour le tour puis vide immédiatement le compositeur."""
        documents = self._specs()
        attachments_html = self._attachment_preview_html(documents)
        self.paths.clear()
        self.page_selections.clear()
        self._show_document(-1)
        return documents, attachments_html

    def _clear_conversation_widgets(self):
        while self.conversation_layout.count():
            item = self.conversation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_conversation(self):
        self._clear_conversation_widgets()
        self.current_assistant_bubble = None
        if not self.turns:
            self.response.hide()
            return
        available = max(180, self.width() - 34)
        bubble_width = max(140, available - 50)
        for turn_index, turn in enumerate(self.turns):
            raw_question = turn.get("question", "")
            if raw_question == "Question audio":
                # Conserve dans l'historique le visuel des barres qui défilait
                # pendant la dictée, plutôt qu'une icône de microphone.
                bars_width, bars_height = 78, 28
                pix = QPixmap(bars_width, bars_height)
                pix.fill(Qt.transparent)
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(Qt.NoPen)
                levels = (0.18, 0.38, 0.68, 0.42, 0.82, 0.55, 0.31, 0.74, 0.48, 0.24, 0.58, 0.35, 0.16)
                bar_width, gap = 3.0, 3.0
                total_width = len(levels) * bar_width + (len(levels) - 1) * gap
                x0 = (bars_width - total_width) / 2.0
                center_y = bars_height / 2.0
                for index, level in enumerate(levels):
                    height = 3.0 + level * (bars_height - 5.0)
                    painter.setBrush(QColor(82, 91, 102, 190))
                    painter.drawRoundedRect(
                        QRectF(x0 + index * (bar_width + gap), center_y - height / 2.0,
                               bar_width, height),
                        bar_width / 2.0, bar_width / 2.0,
                    )
                painter.end()
                bars_path = os.path.join(
                    tempfile.gettempdir(), f"assistant_chat_audio_bars_{os.getpid()}.png"
                )
                pix.save(bars_path, "PNG")
                question = f'<img src="{Path(bars_path).as_uri()}" width="78" height="28" />'
            else:
                question = html.escape(raw_question).replace("\n", "<br>")
            user_row = QWidget(self.conversation_widget)
            user_row.setStyleSheet("background:transparent;border:none;")
            user_layout = QHBoxLayout(user_row)
            user_layout.setContentsMargins(0, 0, 8, 0)
            user_layout.setSpacing(0)
            user_bubble = ChatBubble("user", user_row)
            # Les pièces jointes sont affichées avant la question, comme dans le
            # compositeur, puis la bulle épouse le contenu et reste alignée à droite.
            user_bubble.set_html(turn.get("attachments_html", "") + question)
            user_bubble.fit_to_content_width(bubble_width)
            user_layout.addStretch(1)
            user_layout.addWidget(user_bubble, 0, Qt.AlignRight | Qt.AlignTop)
            self.conversation_layout.addWidget(user_row)

            answer = self._answer_without_sources(turn.get("answer", ""))
            if turn.get("loading", False) and not answer:
                assistant_row = QWidget(self.conversation_widget)
                assistant_row.setStyleSheet("background:transparent;border:none;")
                assistant_layout = QHBoxLayout(assistant_row)
                assistant_layout.setContentsMargins(0, 0, 50, 0)
                assistant_layout.setSpacing(0)
                thinking_bubble = ChatBubble("assistant", assistant_row)
                thinking_bubble.setFixedWidth(78)
                thinking_bubble.browser.hide()
                dots = ThinkingDots(thinking_bubble)
                thinking_bubble.layout().addWidget(dots, 0, Qt.AlignLeft | Qt.AlignVCenter)
                thinking_bubble.setFixedHeight(44)
                assistant_layout.addWidget(thinking_bubble, 0, Qt.AlignLeft | Qt.AlignTop)
                assistant_layout.addStretch(1)
                self.conversation_layout.addWidget(assistant_row)
            if answer:
                rendered = (
                    self.host.markdown_to_html(answer)
                    if self.host is not None
                    else html.escape(answer).replace("\n", "<br>")
                )
                assistant_row = QWidget(self.conversation_widget)
                assistant_row.setStyleSheet("background:transparent;border:none;")
                assistant_layout = QHBoxLayout(assistant_row)
                assistant_layout.setContentsMargins(0, 0, 50, 0)
                assistant_layout.setSpacing(0)
                assistant_bubble = ChatBubble("assistant", assistant_row)
                assistant_bubble.setFixedWidth(bubble_width)
                assistant_bubble.link_clicked.connect(self._open_source_link)
                assistant_bubble.set_html(rendered + turn.get("sources_html", ""))
                if turn_index == self.current_turn_index:
                    self.current_assistant_bubble = assistant_bubble
                assistant_layout.addWidget(assistant_bubble, 1)
                self.conversation_layout.addWidget(assistant_row)
        self.response.show()
        self.conversation_widget.adjustSize()
        QTimer.singleShot(0, self._update_height)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar=self.response.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_height(self):
        self.layout().activate()
        self.composer.layout().activate()
        self.content_widget.layout().activate()

        response_h = 0
        if self.response.isVisible():
            self.conversation_layout.activate()
            doc_h = self.conversation_layout.sizeHint().height() + 4
            if self.streaming_response_active:
                # Une hauteur stable évite la recomposition répétée de la fenêtre
                # translucide/Acrylic pendant l'arrivée des tokens.
                response_h = self.MAX_RESPONSE_HEIGHT
            else:
                response_h = max(45, min(self.MAX_RESPONSE_HEIGHT, doc_h))
            self.response.setFixedHeight(response_h)
        else:
            self.response.setFixedHeight(0)

        # The response and composer are stacked vertically. Computing the height
        # explicitly avoids the conversation being painted behind the composer.
        header_h = 36
        separator_h = 1 if self.header_separator.isVisible() else 0
        top_bottom_margins = 14
        content_spacing = 4 if response_h else 0
        composer_h = max(38, self.composer.sizeHint().height())
        target = header_h + separator_h + top_bottom_margins + content_spacing + response_h + composer_h + 2
        target = max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, target))

        if not self.is_collapsed and abs(self.height() - target) > 2:
            self.setFixedHeight(target)
            self.expanded_height = target

    def _add_sources_html(self, answer, documents):
        if fitz is None or not answer.strip(): return ""
        by_name={}
        for document in documents:
            path=document.get("path") if isinstance(document,dict) else document
            if path: by_name[os.path.basename(path).casefold()]=path
        citations=re.findall(r"([^\n/\\]+?\.pdf)\s*[—-]\s*(?:p(?:age)?\.?\s*)?(\d+)(?:\s*\n+\s*>?\s*(?:Extrait\s*:\s*)?([^\n]+))?",answer,re.IGNORECASE)
        cards=[]
        for index,(filename,page_text,excerpt) in enumerate(citations):
            path=by_name.get(os.path.basename(filename.strip()).casefold())
            if not path: continue
            try:
                doc=fitz.open(path); total=doc.page_count; page_number=max(1,int(page_text))
                if page_number>total: doc.close(); continue
                page=doc.load_page(page_number-1); needle=excerpt.strip().strip(" \t\r\n\"'«»"); rects=page.search_for(needle) if len(needle)>=8 else []
                if not rects and len(needle)>80: rects=page.search_for(needle[:80])
                clip=page.rect
                if rects:
                    union=fitz.Rect(rects[0])
                    for rect in rects[1:]: union|=rect
                    clip=fitz.Rect(max(page.rect.x0,union.x0-28),max(page.rect.y0,union.y0-42),min(page.rect.x1,union.x1+28),min(page.rect.y1,union.y1+42))
                    highlight=page.add_highlight_annot(rects); highlight.set_colors(stroke=(0.55, 0.92, 0.66)); highlight.update()
                # Conserve une capture haute définition distincte pour la loupe
                # et la fenêtre x2. Les anciens tours ne sont plus écrasés car le
                # nom contient un identifiant unique par capture.
                capture_id = f"{time.monotonic_ns()}_{index}"
                pix=page.get_pixmap(matrix=fitz.Matrix(3.0,3.0),clip=clip,alpha=False,annots=True)
                image_path=os.path.join(tempfile.gettempdir(),f"assistant_source_{os.getpid()}_{capture_id}.png")
                pix.save(image_path); doc.close()
                source_pixmap=QPixmap(image_path)
                max_w=max(120,self.width()-82)
                display_w=min(source_pixmap.width(), max_w)
                display_h=max(1, round(source_pixmap.height() * display_w / max(1, source_pixmap.width())))
                token=base64.urlsafe_b64encode(os.path.basename(path).encode("utf-8")).decode("ascii").rstrip("=")
                href=f"source:{page_number}:{token}"; uri=Path(image_path).as_uri(); title=html.escape(os.path.splitext(os.path.basename(path))[0])
                source_title = f"{os.path.splitext(os.path.basename(path))[0]} (Page {page_number}/{total})"
                image_payload = json.dumps(
                    {"path": image_path, "title": source_title},
                    ensure_ascii=False,
                ).encode("utf-8")
                image_token = base64.urlsafe_b64encode(image_payload).decode("ascii").rstrip("=")
                image_href = f"sourceimage:{image_token}"
                cards.append(
                    f'<div style="margin-top:12px; padding-top:9px; border-top:1px solid #C9E8D3;">'
                    f'<div style="font-size:10px; font-style:italic; color:#526B5B;">'
                    f'Source : <a href="{href}" style="color:#397D58; text-decoration:none;">'
                    f'{title} (Page {page_number}/{total})</a></div>'
                    # Le navigateur affiche la capture réduite via width/height,
                    # mais conserve le fichier haute définition comme ressource.
                    # La loupe x2 prélève donc directement des pixels nets.
                    f'<div style="margin-top:8px;"><a href="{image_href}">'
                    f'<img src="{uri}" width="{display_w}" height="{display_h}" />'
                    f'</a></div></div>'
                )
            except Exception: LOGGER.exception("Impossible de générer la capture de la source")
        if not cards: return ""
        return ''.join(cards)

    def show_source_captures(self, answer, documents):
        if not self.turns: return
        sources=self._add_sources_html(answer,documents)
        if sources:
            self.turns[-1]["sources_html"]=sources
            self._render_conversation()

    def _header_press(self,event):
        if event.button()==Qt.LeftButton:
            self._drag_position=event.globalPos()-self.frameGeometry().topLeft(); self._header_press_pos=event.globalPos(); self._header_was_dragged=False; event.accept()
    def _header_move(self,event):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            if self._header_press_pos is not None and (event.globalPos()-self._header_press_pos).manhattanLength()>QApplication.startDragDistance(): self._header_was_dragged=True
            if self._header_was_dragged: self.move(event.globalPos()-self._drag_position)
            event.accept()
    def _header_release(self,event):
        if event.button()==Qt.LeftButton:
            if not self._header_was_dragged: self.toggle_collapse()
            self._drag_position=None; self._header_press_pos=None; self._header_was_dragged=False; event.accept()

    def toggle_collapse(self):
        if self.collapse_animation is not None:
            self.collapse_animation.stop()
            self.collapse_animation.deleteLater()
            self.collapse_animation = None

        current = self.height()
        collapsed_height = 38
        self.setMinimumHeight(collapsed_height)
        if self.is_collapsed:
            target = max(self.MIN_HEIGHT, self.expanded_height)
            self.header_separator.show()
            self.content_widget.show()
            expanding = True
        else:
            self.expanded_height = max(self.MIN_HEIGHT, current)
            self.header_separator.hide()
            target = collapsed_height
            expanding = False

        animation = QPropertyAnimation(self, b"geometry", self)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(self.geometry())
        animation.setEndValue(QRect(self.x(), self.y(), self.width(), target))
        self.collapse_animation = animation

        def done():
            if self.collapse_animation is not animation:
                return
            self.collapse_animation = None
            self.is_collapsed = not expanding
            if expanding:
                self.setMinimumHeight(self.MIN_HEIGHT)
            else:
                self.content_widget.hide()
            animation.deleteLater()

        animation.finished.connect(done)
        animation.start()

    def focus_message_input(self):
        """Place immédiatement le curseur dans « Message assistant IA »."""
        if self.is_collapsed:
            self.toggle_collapse()
        self.raise_()
        self.activateWindow()
        self.question.setFocus(Qt.ShortcutFocusReason)
        cursor = self.question.textCursor()
        cursor.movePosition(cursor.End)
        self.question.setTextCursor(cursor)

    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self._apply_effects)
        QTimer.singleShot(0,self._update_height)
        QTimer.singleShot(0,self.focus_message_input)
    def _apply_effects(self):
        try: apply_acrylic_blur(int(self.winId()),0xB8F5F5F5); apply_rounded_corners(int(self.winId()))
        except Exception: pass

    def _update_question_height(self):
        """Agrandit la saisie jusqu'à trois lignes, puis active son défilement."""
        document = self.question.document()
        document.setTextWidth(max(40, self.question.viewport().width()))
        line_height = max(14, self.question.fontMetrics().lineSpacing())
        minimum_height = 30
        maximum_height = minimum_height + 2 * line_height
        content_height = int(document.size().height()) + 8
        target_height = max(minimum_height, min(maximum_height, content_height))
        self.question.setFixedHeight(target_height)
        self.question.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if content_height > maximum_height else Qt.ScrollBarAlwaysOff
        )
        if content_height > maximum_height:
            bar = self.question.verticalScrollBar()
            bar.setValue(bar.maximum())
        self._update_height()

    def _update_send_visibility(self):
        """Affiche une seule action adaptée à l'état du compositeur."""
        if self.streaming_response_active:
            self.mic.hide()
            self.send.hide()
            self.stop_generation_button.show()
            return
        self.stop_generation_button.hide()
        if self.is_recording:
            self.mic.show()
            self.send.hide()
            return
        has_text = bool(self.question.toPlainText().strip())
        self.mic.setVisible(not has_text)
        self.send.setVisible(has_text)

    def _stop_llm_generation(self):
        """Arrête réellement la génération sans afficher de message intermédiaire."""
        if not self.streaming_response_active:
            return
        self.stop_generation_button.setEnabled(False)
        thread = self.host.document_thread if self.host is not None else None
        if thread is not None and thread.isRunning():
            thread.stop()
        else:
            self.finish_response()
    @staticmethod
    def _supported(path): return os.path.isfile(path) and os.path.splitext(path)[1].lower() in {".pdf",".png",".jpg",".jpeg",".webp",".bmp",".gif",".tif",".tiff"}
    def _dragged_paths(self,event):
        if not event.mimeData().hasUrls(): return []
        return [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and self._supported(u.toLocalFile())]
    def _set_drop_feedback(self,visible):
        if visible:
            self.drop_feedback.setGeometry(1,1,max(1,self.composer.width()-2),max(1,self.composer.height()-2))
            self.drop_feedback.show(); self.drop_feedback.raise_()
        else:self.drop_feedback.hide()
    def eventFilter(self,watched,event):
        if watched is self.composer:
            if event.type() in (QEvent.DragEnter,QEvent.DragMove):
                paths=self._dragged_paths(event); self._set_drop_feedback(bool(paths))
                if paths: event.acceptProposedAction(); return True
            elif event.type()==QEvent.DragLeave:
                self._set_drop_feedback(False); event.accept(); return True
            elif event.type()==QEvent.Drop:
                paths=self._dragged_paths(event); self._set_drop_feedback(False)
                if paths: self._add_paths(paths); event.acceptProposedAction(); return True
        return super().eventFilter(watched,event)
    def dragEnterEvent(self,event):
        paths=self._dragged_paths(event); self._set_drop_feedback(bool(paths))
        if paths:event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):
        if self._dragged_paths(event):self._set_drop_feedback(True); event.acceptProposedAction()
        else:event.ignore()
    def dragLeaveEvent(self,event):
        self._set_drop_feedback(False); event.accept()
    def dropEvent(self,event):
        paths=self._dragged_paths(event); self._set_drop_feedback(False)
        if paths:self._add_paths(paths); event.acceptProposedAction()
        else:event.ignore()
    def _choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Ajouter des documents","","Documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        self._add_paths(paths)
    def _page_count(self,path):
        if path.lower().endswith('.pdf') and fitz is not None:
            doc=fitz.open(path)
            try:return max(1,doc.page_count)
            finally:doc.close()
        return 1
    def _add_paths(self,paths):
        for path in paths:
            path=os.path.abspath(path)
            if self._supported(path) and path not in self.paths:
                count=self._page_count(path); self.paths.append(path); self.page_selections[path]=(1,count)
        if self.paths:self._show_document(len(self.paths)-1)
    def _clear_image_strip(self):
        while self.image_strip_layout.count():
            w=self.image_strip_layout.takeAt(0).widget()
            if w:w.deleteLater()
    def _remove_path(self,path):
        if path in self.paths:self.paths.remove(path); self.page_selections.pop(path,None)
        self._show_document(len(self.paths)-1)
    def _rebuild_image_strip(self):
        """Affiche chaque pièce jointe dans une carte à contour gris arrondi."""
        self._clear_image_strip()
        cell_w, cell_h = 104, 110
        preview_w, pdf_preview_h = 86, 66
        pdf_title_y, pdf_title_h = 68, 15
        page_row_y, page_row_h = 82, 25

        for path in self.paths:
            is_pdf = path.lower().endswith('.pdf')
            holder = AttachmentPreviewWidget(self.image_strip)
            holder.setFixedSize(cell_w, cell_h)
            if is_pdf:
                count = self._page_count(path)
                first, last = self.page_selections.get(path, (1, count))
                source = QPixmap()
                if fitz is not None:
                    try:
                        doc = fitz.open(path)
                        try:
                            pix = doc.load_page(max(0, first - 1)).get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                            source.loadFromData(pix.tobytes('png'))
                        finally:
                            doc.close()
                    except Exception:
                        LOGGER.exception("Impossible de générer la vignette PDF")
                if source.isNull():
                    source = QPixmap(preview_w, pdf_preview_h - 6); source.fill(QColor('#EEF3F8'))
                shown = source.scaled(preview_w, pdf_preview_h - 6, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = (cell_w - shown.width()) // 2
                y = 4 + max(0, (pdf_preview_h - 6 - shown.height()) // 2)
                rounded = QPixmap(shown.size()); rounded.fill(Qt.transparent)
                painter = QPainter(rounded); painter.setRenderHint(QPainter.Antialiasing, True)
                clip = QPainterPath(); clip.addRoundedRect(QRectF(rounded.rect()), 6, 6)
                painter.setClipPath(clip); painter.drawPixmap(0, 0, shown); painter.end()
                label = QLabel(holder); label.setPixmap(rounded); label.setGeometry(x, y, shown.width(), shown.height())

                pdf_name = Path(path).stem
                displayed_name = pdf_name if len(pdf_name) <= 12 else pdf_name[:12] + "..."
                name_label = QLabel(displayed_name, holder)
                name_label.setGeometry(4, pdf_title_y, cell_w - 8, pdf_title_h)
                name_label.setAlignment(Qt.AlignCenter); name_label.setToolTip(pdf_name)
                name_label.setStyleSheet("QLabel{background:transparent;border:none;color:#354454;font-size:10px;font-weight:600;padding:0;margin:0;}")

                pages = QWidget(holder); pages.setGeometry(0, page_row_y, cell_w, page_row_h)
                row = QHBoxLayout(pages); row.setContentsMargins(15, 0, 15, 1); row.setSpacing(0)
                first_edit, last_edit = QLineEdit(str(first)), QLineEdit(str(last))
                for edit in (first_edit, last_edit):
                    edit.setAlignment(Qt.AlignCenter); edit.setFixedSize(24, 19)
                    edit.setStyleSheet("QLineEdit{background:transparent;border:1px solid transparent;border-radius:4px;padding:0;margin:0;font-size:10px;}QLineEdit:hover{background:rgba(255,255,255,175);border:1px solid rgba(0,0,0,45);}QLineEdit:focus{background:#FFFFFF;border:1px solid rgba(0,0,0,70);}")
                dash = QLabel("-"); dash.setAlignment(Qt.AlignCenter); dash.setFixedSize(10, 19)
                dash.setStyleSheet("QLabel{background:transparent;border:none;padding:0;margin:0;font-size:10px;}")
                row.addStretch(1); row.addWidget(first_edit); row.addWidget(dash); row.addWidget(last_edit); row.addStretch(1)
                def save_range(_path=path, _first=first_edit, _last=last_edit):
                    total = self._page_count(_path)
                    try: a, b = int(_first.text()), int(_last.text())
                    except ValueError: a, b = self.page_selections.get(_path, (1, total))
                    a = max(1, min(a, total)); b = max(a, min(b, total))
                    self.page_selections[_path] = (a, b); self._rebuild_image_strip(); self._update_height()
                first_edit.editingFinished.connect(save_range); last_edit.editingFinished.connect(save_range)
            else:
                source = QPixmap(path)
                if source.isNull(): holder.deleteLater(); continue
                shown = source.scaled(preview_w, cell_h - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                rounded = QPixmap(shown.size()); rounded.fill(Qt.transparent)
                painter = QPainter(rounded); painter.setRenderHint(QPainter.Antialiasing, True)
                clip = QPainterPath(); clip.addRoundedRect(QRectF(rounded.rect()), 7, 7)
                painter.setClipPath(clip); painter.drawPixmap(0, 0, shown); painter.end()
                x, y = (cell_w - shown.width()) // 2, (cell_h - shown.height()) // 2
                label = QLabel(holder); label.setPixmap(rounded); label.setGeometry(x, y, shown.width(), shown.height())
            close = QPushButton("×", holder); close.setFixedSize(20, 20); close.move(cell_w - 22, 2)
            close.setCursor(Qt.PointingHandCursor)
            close.setStyleSheet("QPushButton{background:#747B84;color:white;border:1px solid #F3F4F6;border-radius:10px;padding:0;font-size:15px;font-weight:600;}QPushButton:hover{background:#5E6670;}")
            close.clicked.connect(lambda _=False, p=path: self._remove_path(p)); holder.set_close_button(close)
            self.image_strip_layout.addWidget(holder)

        margins = self.image_strip_layout.contentsMargins(); spacing = self.image_strip_layout.spacing()
        total_width = margins.left() + margins.right() + len(self.paths) * cell_w + max(0, len(self.paths) - 1) * spacing
        self.image_strip.setFixedSize(max(1, total_width), 116)
        self.image_scroll.setVisible(bool(self.paths)); self.document_area.setVisible(bool(self.paths))
        self.image_strip.adjustSize(); self.image_scroll.viewport().updateGeometry()

    def _show_document(self,index=-1):
        if not self.paths:
            self._clear_image_strip(); self.image_scroll.hide(); self.document_area.hide(); self.status.hide(); self._update_height(); return
        self._rebuild_image_strip(); self.status.setText("Pièces jointes prêtes"); self._update_height()
    def _save_page_range(self):
        return
    def _remove_current(self):
        if self.paths:
            path=self.paths.pop(); self.page_selections.pop(path,None); self._show_document(len(self.paths)-1)
    def _specs(self):
        return [{"path":p,"pages":list(range(self.page_selections[p][0],self.page_selections[p][1]+1))} for p in self.paths]

    def begin_response(self, question, attachments_html=""):
        self.streaming_response_active = True
        self.current_assistant_bubble = None
        self.turns.append({
            "question": question,
            "answer": "",
            "sources_html": "",
            "attachments_html": attachments_html,
            "loading": True,
        })
        self.current_turn_index = len(self.turns) - 1
        self.response.show()
        self._render_conversation()
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
    def append_response(self,text):
        if self.current_turn_index < 0:
            return
        turn = self.turns[self.current_turn_index]
        turn["answer"] += text
        # Dès le premier fragment, les points disparaissent. Le rendu est ensuite
        # limité à environ 22 mises à jour par seconde pour supprimer scintillement,
        # sauts de largeur et pertes temporaires de la barre de défilement.
        turn["loading"] = False
        self.pending_stream_render = True
        if not self.stream_render_timer.isActive():
            self.stream_render_timer.start()

    def _flush_stream_render(self):
        if not self.pending_stream_render:
            return
        self.pending_stream_render = False
        if self.current_turn_index < 0:
            return
        turn = self.turns[self.current_turn_index]
        answer = self._answer_without_sources(turn.get("answer", ""))
        rendered = (
            self.host.markdown_to_html(answer)
            if self.host is not None
            else html.escape(answer).replace("\n", "<br>")
        )
        try:
            bubble_is_valid = (
                self.current_assistant_bubble is not None
                and self.current_assistant_bubble.parent() is not None
            )
        except RuntimeError:
            bubble_is_valid = False
        if not bubble_is_valid:
            # Premier fragment uniquement : remplace les points par la bulle.
            self._render_conversation()
        else:
            # Fragments suivants : mise à jour du QTextBrowser existant, sans
            # supprimer ni recréer les widgets de la conversation.
            self.current_assistant_bubble.set_html(
                rendered + turn.get("sources_html", "")
            )
            self.conversation_layout.activate()
            self.conversation_widget.adjustSize()
            self._scroll_to_bottom()

    def finish_response(self):
        self.streaming_response_active = False
        self.stream_render_timer.stop()
        self.pending_stream_render = False
        if self.current_turn_index>=0:
            self.turns[self.current_turn_index]["loading"]=False
        self.status.clear(); self.status.hide()
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
        self._render_conversation()
    def show_error(self,message):
        self.streaming_response_active = False
        if self.current_turn_index>=0:
            self.turns[self.current_turn_index]["loading"]=False; self.turns[self.current_turn_index]["answer"] += f"\n\n⚠️ {message}"
        self.status.setText("Erreur d'analyse")
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
        self._render_conversation()

    def _ask_text(self):
        question = self.question.toPlainText().strip()
        if not question:
            self.status.setText("Saisissez une question ou utilisez le microphone")
            return
        documents, attachments_html = self._take_current_attachments()
        self.begin_response(question, attachments_html)
        self.question.clear()
        self.ask_requested.emit(documents, question, None)
    def _set_inline_recording_visual(self,active):
        self.question.setVisible(not active)
        # Un clic pendant la dictée termine l'enregistrement puis envoie
        # l'audio. L'icône Envoyer correspond donc à l'action réelle.
        self.mic.kind="send" if active else "mic"
        self.mic.update()
        self.audio_bars.start() if active else self.audio_bars.stop()
        self._update_send_visibility()
        self._update_height()
    def _toggle_microphone(self):
        if self.is_recording:
            if self.audio_thread and self.audio_thread.isRunning():self.audio_thread.stop_recording()
            self.status.setText("Traitement de la question audio..."); return
        voice=self.host.config.get("voice_input",{}) if self.host else {}; self.is_recording=True; self._set_inline_recording_visual(True)
        device=self.host._selected_voice_device() if self.host else None
        self.audio_thread=AudioRecorderThread(device,voice.get("sample_rate",16000),voice.get("maximum_duration",60.0),release_tail_ms=voice.get("release_tail_ms",700),microphone_gain=voice.get("microphone_gain",2.0),parent=self)
        self.audio_thread.level_changed.connect(self.audio_bars.set_level); self.audio_thread.recorded.connect(self._audio_ready); self.audio_thread.error.connect(self._audio_error); self.audio_thread.start()
    def _audio_ready(self, data, duration, rms):
        self.is_recording = False
        self.audio_thread = None
        self._set_inline_recording_visual(False)
        if not data or duration < 0.3:
            self.status.setText("Aucun son détecté")
            return
        documents, attachments_html = self._take_current_attachments()
        self.begin_response("Question audio", attachments_html)
        self.ask_requested.emit(documents, "", data)
    def _audio_error(self,message):
        self.is_recording=False; self.audio_thread=None; self._set_inline_recording_visual(False); self.status.setText(message)

# ==========================================
# FENÊTRE FLOTTANTE AVEC BLUR
# ==========================================
class AssistantWindow(QWidget):
    show_menu_signal = pyqtSignal()
    trigger_direct_signal = pyqtSignal(int)
    toggle_collapse_signal = pyqtSignal()
    voice_press_signal = pyqtSignal(int)
    voice_release_signal = pyqtSignal(int)
    voice_cancel_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = load_config()
        # Gestionnaire des skills utilisé par le mode Agent.
        self.skill_manager = SkillManager()
        self.loaded_skills = self.skill_manager.discover()
        LOGGER.info(
            "Skills chargés : %s",
            ", ".join(self.loaded_skills) if self.loaded_skills else "aucun"
        )
        if self.config.get('llama_server', {}).get('auto_start', True):
            ok, message = LLAMA_SERVER_MANAGER.start(self.config)
            print(f"llama.cpp : {message}")

        # Précharge Kokoro en arrière-plan pour que la première lecture
        # vocale soit aussi rapide que les suivantes.
        self.kokoro_warmup_thread = KokoroWarmupThread(self.config, self)
        self.kokoro_warmup_thread.start()
        self.selected_text = ""
        self.thread = None
        self.drag_position = None
        self.header_press_global_pos = None
        self.header_was_dragged = False
        self.response_text = ""
        self.is_collapsed = False
        self.is_generating = False
        self.expanded_height = 100
        self.collapse_animation = None
        self.runtime_info_thread = None
        self.runtime_info_dialog = None
        self.audio_thread = None
        self.tts_thread = None
        # File de synthèse incrémentale : la première phrase est lue pendant
        # que llama.cpp continue de générer la suite de la réponse.
        self.tts_queue = []
        self.tts_stream_buffer = ""
        self.tts_streaming_auto = False
        self.voice_sending = False
        self.request_failed = False
        self.voice_cancelled = False
        self.voice_action_index = None
        self.current_request_is_audio = False
        self.document_thread = None
        self.document_dialog = None
        self.document_source_pages = []
        self.document_documents = []
        # Documents cumulés de la conversation Ctrl+9. Ils restent disponibles
        # pour toutes les questions de suivi, même sans nouvelle pièce jointe.
        self.document_session_documents = []
        self.document_response_active = False
        self.document_history = []
        self.recording_indicator = RecordingIndicator()
        self.recording_indicator.cancel_requested.connect(self.cancel_voice_operation)

        # Animation d'attente avec des points successifs : ., .., ...
        self.loading_action_name = ""
        self.loading_dot_count = 0
        self.last_action_cfg = None
        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(400)
        self.loading_timer.timeout.connect(self.update_loading_animation)

        # Regroupe les fragments SSE pendant quelques millisecondes pour eviter
        # un rendu HTML et un redimensionnement couteux a chaque token.
        self.pending_stream_text = ""
        self.last_stream_resize_at = 0.0
        self.stream_render_timer = QTimer(self)
        self.stream_render_timer.setSingleShot(True)
        self.stream_render_timer.setInterval(25)
        self.stream_render_timer.timeout.connect(self.flush_stream_text)

        self.initUI()

        self.show_menu_signal.connect(self._show_menu_impl)
        self.trigger_direct_signal.connect(self._execute_direct_impl)
        self.toggle_collapse_signal.connect(self.toggle_open_window_collapse)
        self.voice_press_signal.connect(self.start_voice_recording)
        self.voice_release_signal.connect(self.stop_voice_recording)
        self.voice_cancel_signal.connect(self.cancel_voice_operation)

    def show_runtime_information(self):
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
        if LLAMA_SERVER_MANAGER.is_running():
            process_ids.add(LLAMA_SERVER_MANAGER.process.pid)

        self.runtime_info_thread = RuntimeInfoThread(
            self.config.get("api_url", ""), process_ids, self
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

    def start_server_online_notification(self, tray_icon):
        """Surveille le serveur au démarrage et notifie l'utilisateur lorsqu'il est prêt."""
        self.startup_tray_icon = tray_icon
        self.startup_server_notified = False
        self.startup_status_thread = None
        self.startup_status_timer = QTimer(self)
        self.startup_status_timer.setInterval(1500)
        self.startup_status_timer.timeout.connect(self.check_startup_server_status)
        self.startup_status_timer.start()
        QTimer.singleShot(0, self.check_startup_server_status)

    def check_startup_server_status(self):
        if self.startup_server_notified:
            return
        if self.startup_status_thread is not None and self.startup_status_thread.isRunning():
            return
        self.startup_status_thread = ServerStatusThread(self.config.get('api_url', ''), self)
        self.startup_status_thread.status_checked.connect(self.handle_startup_server_status)
        self.startup_status_thread.finished.connect(self.on_startup_status_finished)
        self.startup_status_thread.start()

    def on_startup_status_finished(self):
        """Libère la référence afin d'autoriser le contrôle suivant."""
        thread = self.sender()
        if thread is self.startup_status_thread:
            self.startup_status_thread = None
        if thread is not None:
            thread.deleteLater()

    def handle_startup_server_status(self, online, detail, model_name):
        if not online or self.startup_server_notified:
            return
        self.startup_server_notified = True
        self.startup_status_timer.stop()

        message = "Le serveur est en ligne et prêt à recevoir des requêtes."
        if model_name and model_name != "Modèle inconnu":
            displayed_model_name = re.sub(r"\.gguf$", "", model_name, flags=re.IGNORECASE)
            message += f"\nModèle : {displayed_model_name}"

        self.startup_tray_icon.showMessage(
            "",
            message,
            self.startup_tray_icon.icon(),
            5000
        )

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("AssistantWindow")

        self.resize(390, 35)
        self.setMinimumSize(250, 35)
        self.setMaximumSize(1400, 900)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        self.panel.setStyleSheet("""
            QFrame#AcrylicPanel {
                background-color: rgba(255, 255, 255, 34);
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 16px;
            }
            QFrame#Header {
                background-color: transparent;
                border: none;
            }
            QLabel#TitleLabel {
                background: transparent; color: #171717; border: none; padding: 0;
                font-family: 'Aptos Display', 'Segoe UI Variable Display', 'Segoe UI', Arial; font-size: 13px; font-weight: 700;
            }
            QPushButton#HeaderIconButton {
                background-color: transparent;
                border: none;
                border-radius: 14px;
                padding: 0;
                margin: 0;
                text-align: center;
            }
            QPushButton#HeaderIconButton:hover,
            QPushButton#HeaderIconButton:pressed,
            QPushButton#HeaderIconButton:focus { background: transparent; border: none; outline: none; }
            QScrollArea, QScrollArea QWidget, QScrollArea QViewport { background: transparent; border: none; }
            QScrollBar:vertical { background: rgba(0, 0, 0, 14); width: 10px; margin: 4px 3px 8px 0; border-radius: 5px; }
            QScrollBar::handle:vertical { background: rgba(30, 30, 30, 85); min-height: 26px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: rgba(30, 30, 30, 135); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: transparent; }
        """)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame(self.panel)
        header.setObjectName("Header")
        header.setFixedHeight(36)
        header.mousePressEvent = self.mousePressEvent
        header.mouseMoveEvent = self.mouseMoveEvent
        header.mouseReleaseEvent = self.mouseReleaseEvent
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 1, 3, 0)
        header_layout.setSpacing(3)
        header_layout.setAlignment(Qt.AlignVCenter)

        self.header_icon_label = QLabel(header)
        self.header_icon_label.setFixedSize(18, 18)
        self.header_icon_label.setAlignment(Qt.AlignCenter)
        header_icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assistant_icon.webp"
        )
        header_icon = QIcon(header_icon_path)
        if header_icon.isNull():
            fallback_svg = (
                '<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 '
                'C7.5 12.8 11.2 16.5 12 22.5 '
                'C12.8 16.5 16.5 12.8 22.5 12 '
                'C16.5 11.2 12.8 7.5 12 1.5z"/>'
            )
            header_icon = create_svg_icon(fallback_svg, "#FFFFFF")
        self.header_icon_label.setPixmap(header_icon.pixmap(16, 16))
        header_layout.addWidget(self.header_icon_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel("Transcript", header)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setTextFormat(Qt.PlainText)
        header_layout.addWidget(self.title_label, 1)

        self.speak_button = QPushButton(header)
        self.speak_button.setObjectName("HeaderIconButton")
        self.speak_button.setFlat(True)
        self.speak_button.setIcon(ICONS_DARK["speak"])
        self.speak_button.setIconSize(QSize(18, 18))
        self.speak_button.setFixedSize(27, 28)
        self.speak_button.setToolTip("Lire la réponse à haute voix")
        self.speak_button.setCursor(Qt.PointingHandCursor)
        self.speak_button.clicked.connect(self.toggle_speech)
        header_layout.addWidget(self.speak_button, 0, Qt.AlignVCenter)

        self.copy_button = QPushButton(header)
        self.copy_button.setObjectName("HeaderIconButton")
        self.copy_button.setFlat(True)
        self.copy_button.setAutoFillBackground(False)
        self.copy_button.setIcon(ICONS_DARK["copy"])
        self.copy_button.setIconSize(QSize(17, 17))
        self.copy_button.setFixedSize(27, 28)
        self.copy_button.setToolTip("Copier la réponse")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.clicked.connect(self.copy_response)
        header_layout.addWidget(self.copy_button, 0, Qt.AlignVCenter)

        self.close_button = QPushButton(header)
        self.close_button.setObjectName("HeaderIconButton")
        self.close_button.setFlat(True)
        self.close_button.setAutoFillBackground(False)
        self.close_button.setIcon(ICONS_DARK["close"])
        self.close_button.setIconSize(QSize(19, 19))
        self.close_button.setFixedSize(27, 28)
        self.close_button.setToolTip("Fermer")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.clicked.connect(self.close_response_window)
        header_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)
        panel_layout.addWidget(header)
        self.separator_container = QWidget(self.panel)
        self.separator_container.setFixedHeight(3)
        sep_layout = QHBoxLayout(self.separator_container)
        sep_layout.setContentsMargins(14, 0, 14, 0)
        separator = QFrame(self.separator_container)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(0,0,0,35); border: none;")
        sep_layout.addWidget(separator)
        panel_layout.addWidget(self.separator_container)

        self.scroll_area = QScrollArea(self.panel)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.viewport().setAutoFillBackground(False)

        self.label = QLabel("Attente...")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self.label.setOpenExternalLinks(False)
        self.label.linkActivated.connect(self.open_response_link)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setContentsMargins(0, 0, 0, 0)
        self.label.setMinimumWidth(0)
        self.label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #111111;
                padding: 7px 15px 7px 10px;
                font-family: 'Aptos', 'Segoe UI Variable Text', 'Segoe UI', Arial;
                font-size: 13px;
                line-height: 1.5;
            }
        """)

        pal = self.label.palette()
        pal.setColor(QPalette.Highlight, QColor(170, 170, 170))
        pal.setColor(QPalette.HighlightedText, QColor(17, 17, 17))
        self.label.setPalette(pal)
        self.scroll_area.setWidget(self.label)
        panel_layout.addWidget(self.scroll_area, 1)

        # Visible uniquement pendant l'exécution d'un outil.
        self.tool_status_label = QLabel("", self.panel)
        self.tool_status_label.setTextFormat(Qt.PlainText)
        self.tool_status_label.setStyleSheet(
            "QLabel{background:rgba(37,99,184,18);color:#245A91;"
            "border:none;padding:5px 10px;font-size:11px;font-style:italic;}"
        )
        self.tool_status_label.hide()
        panel_layout.addWidget(self.tool_status_label)

        self.layout.addWidget(self.panel)

    def nativeEvent(self, event_type, message):
        # Aucun traitement natif de redimensionnement : la fenêtre peut
        # être déplacée par son en-tête, mais sa largeur et sa hauteur ne sont
        # plus modifiables manuellement depuis les bords ou les coins.
        return super().nativeEvent(event_type, message)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.header_press_global_pos = event.globalPos()
            self.header_was_dragged = False
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_position is not None and event.buttons() & Qt.LeftButton:
            if self.header_press_global_pos is not None:
                distance = (event.globalPos() - self.header_press_global_pos).manhattanLength()
                if distance >= QApplication.startDragDistance():
                    self.header_was_dragged = True
            if self.header_was_dragged:
                self.move(event.globalPos() - self.drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag_position is not None:
            was_dragged = self.header_was_dragged
            self.drag_position = None
            self.header_press_global_pos = None
            self.header_was_dragged = False

            # Un clic simple sur la barre de titre replie ou déploie la fenêtre.
            # Un glissement déplace la fenêtre sans modifier son état.
            if not was_dragged:
                if self.is_collapsed:
                    self.expanded_height = self.calculate_expanded_height()
                    self.animate_height(self.expanded_height, True)
                else:
                    self.animate_height(38, False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def update_rounded_mask(self):
        radius = 16.0
        path = QPainterPath(); path.addRoundedRect(QRectF(self.rect()), radius, radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        panel_path = QPainterPath(); panel_path.addRoundedRect(QRectF(self.panel.rect()), radius, radius)
        self.panel.setMask(QRegion(panel_path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_rounded_mask()

    def stop_height_animation(self):
        """Arrête proprement l'animation avant tout redimensionnement manuel."""
        if self.collapse_animation is not None:
            self.collapse_animation.stop()
            self.collapse_animation.deleteLater()
            self.collapse_animation = None

    def calculate_expanded_height(self):
        """Calcule la hauteur utile à partir du contenu réellement affiché."""
        self.label.adjustSize()
        content_height = self.label.sizeHint().height() + 52
        maximum_height = max(150, int(self.width() * 9 / 16))
        return max(70, min(maximum_height, content_height))

    def animate_height(self, target, expanding):
        self.stop_height_animation()
        current = self.geometry()
        fixed_top = current.top()

        # L'état cible est enregistré immédiatement pour éviter qu'une animation
        # interrompue laisse is_collapsed incohérent avec la géométrie réelle.
        self.is_collapsed = not expanding
        if expanding:
            self.separator_container.show()
            self.scroll_area.show()
            target = max(70, target)
        else:
            # La hauteur développée ne doit jamais provenir d'une image
            # intermédiaire de l'animation de réduction.
            self.expanded_height = self.calculate_expanded_height()
            target = 38

        animation = QPropertyAnimation(self, b"geometry", self)
        self.collapse_animation = animation
        animation.setDuration(300)
        animation.setStartValue(current)
        animation.setEndValue(
            QRect(current.left(), fixed_top, current.width(), target)
        )
        animation.setEasingCurve(QEasingCurve.InOutCubic)

        def done():
            # Ignore le callback d'une ancienne animation déjà remplacée.
            if self.collapse_animation is not animation:
                return
            self.collapse_animation = None
            if expanding:
                self.resize(self.width(), target)
                self.separator_container.show()
                self.scroll_area.show()
            else:
                self.separator_container.hide()
                self.scroll_area.hide()
            self.move(self.x(), fixed_top)
            self.update_rounded_mask()
            animation.deleteLater()

        animation.finished.connect(done)
        animation.start()

    def enterEvent(self, event):
        # Le survol ne modifie plus l'état de la fenêtre.
        super().enterEvent(event)

    def leaveEvent(self, event):
        # La sortie du pointeur ne replie plus la fenêtre.
        super().leaveEvent(event)

    def get_selected_text(self):
        """Copie de façon fiable le texte sélectionné, y compris dans les lecteurs PDF."""
        try:
            clipboard_backup = pyperclip.paste()
        except Exception:
            clipboard_backup = ""

        marker = f"__ASSISTANT_COPY_{time.monotonic_ns()}__"

        def read_new_clipboard(timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                time.sleep(0.04)
                try:
                    value = pyperclip.paste()
                except Exception:
                    continue
                if value != marker:
                    return str(value).rstrip("\r\n")
            return ""

        try:
            # Le raccourci global contient Ctrl. Certains lecteurs PDF, notamment
            # Acrobat, ignorent Ctrl+C si la touche du raccourci est encore enfoncée.
            deadline = time.monotonic() + 1.0
            while keyboard.is_pressed('ctrl') and time.monotonic() < deadline:
                time.sleep(0.02)

            # Libère les modificateurs susceptibles d'être restés actifs, puis
            # laisse au lecteur PDF le temps de récupérer son focus clavier.
            for key in ('ctrl', 'shift', 'alt'):
                try:
                    keyboard.release(key)
                except Exception:
                    pass
            time.sleep(0.12)

            # Plusieurs tentatives sont utiles avec les PDF volumineux ou les
            # lecteurs exécutés en mode protégé, dont le presse-papiers est lent.
            for shortcut, timeout in (('ctrl+c', 1.8), ('ctrl+c', 1.8), ('ctrl+insert', 1.8)):
                pyperclip.copy(marker)
                time.sleep(0.06)
                keyboard.send(shortcut)
                copied = read_new_clipboard(timeout)
                if copied:
                    return copied
                time.sleep(0.10)
            return ""
        finally:
            try:
                pyperclip.copy(clipboard_backup)
            except Exception:
                pass

    def _show_menu_impl(self):
        self.selected_text = self.get_selected_text()
        self.update_window_title()

        menu = QMenu(self)
        menu.setObjectName("AssistantMenu")
        menu.setAttribute(Qt.WA_TranslucentBackground, False)
        menu.setAutoFillBackground(True)
        menu.setStyleSheet("""
            QMenu#AssistantMenu {
                background-color: #FFFFFF;
                color: #111111;
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 8px;
                padding: 8px;
                font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
                font-size: 13px;
            }
            QMenu#AssistantMenu::item {
                background-color: transparent;
                color: #111111;
                min-height: 22px;
                padding: 7px 22px 7px 12px;
                margin: 2px;
                border: none;
                border-radius: 6px;
            }
            QMenu#AssistantMenu::item:selected {
                background-color: rgba(8, 74, 144, 150);
                color: #FFFFFF;
            }
            QMenu#AssistantMenu::separator {
                height: 1px;
                background-color: rgba(0, 0, 0, 35);
                margin: 6px 10px;
            }
        """)

        for i, action in enumerate(self.config['actions']):
            display_name = action['name']
            if i < 9:
                display_name = f"{i+1}  •  {display_name}"
            act = QAction(display_name, self)
            act.triggered.connect(lambda checked, a=action: self.execute_action(a))
            menu.addAction(act)

        menu.addSeparator()
        document_action = QAction("9  •  Interroger mes documents", self)
        document_action.triggered.connect(self.show_document_dialog)
        menu.addAction(document_action)

        menu.addSeparator()

        action_param = QAction("Paramètres", self)
        action_param.triggered.connect(self.open_settings)
        menu.addAction(action_param)

        action_quit = QAction("Quitter", self)
        action_quit.triggered.connect(self.quit_application)
        menu.addAction(action_quit)

        menu.winId()
        apply_rounded_corners(int(menu.winId()))

        cursor_pos = QCursor.pos()
        menu.exec_(cursor_pos)

    def toggle_open_window_collapse(self):
        """Ctrl+0 replie ou déplie la fenêtre de l'assistant actuellement ouverte."""
        if self.document_dialog is not None and self.document_dialog.isVisible():
            self.document_dialog.toggle_collapse()
            return
        if not self.isVisible():
            return
        if self.is_collapsed:
            self.expanded_height = self.calculate_expanded_height()
            self.animate_height(self.expanded_height, True)
        else:
            self.animate_height(38, False)

    def _execute_direct_impl(self, index):
        """Ctrl+N utilise le texte sélectionné ; Ctrl+9 ouvre l'analyse documentaire."""
        if index == 8:
            self.show_document_dialog()
            return
        if not 0 <= index < len(self.config["actions"]):
            return
        self.trigger_action(index)

    def show_document_dialog(self):
        """Ouvre la fenêtre Document intégrée utilisée par Ctrl+9."""
        if self.document_dialog is not None and self.document_dialog.isVisible():
            self.document_dialog.raise_()
            self.document_dialog.activateWindow()
            QTimer.singleShot(0, self.document_dialog.focus_message_input)
            return
        self.document_history = []
        self.document_session_documents = []
        self.document_dialog = DocumentDialog(self)
        self.document_dialog.ask_requested.connect(self.start_document_analysis)
        self.document_dialog.finished.connect(lambda _result: setattr(self, "document_dialog", None))
        self.document_dialog.show()
        QTimer.singleShot(0, self.document_dialog.focus_message_input)

    def start_document_analysis(self, paths, question, audio_data=None):
        """Analyse une nouvelle question en conservant l'historique de la conversation."""
        if self.document_thread is not None and self.document_thread.isRunning():
            return
        self.stop_generation(); self.stop_speech(); self.response_text=""; self.request_failed=False
        self.document_response_active=True; self.document_source_pages=[]
        # Ajoute les nouvelles pièces jointes au corpus de session sans doublon.
        # Une question de suivi sans fichier réutilise donc automatiquement le
        # même corpus et doit à nouveau produire ses citations et captures.
        known = {
            (item.get("path") if isinstance(item, dict) else item): index
            for index, item in enumerate(self.document_session_documents)
        }
        for item in paths:
            item_path = item.get("path") if isinstance(item, dict) else item
            if item_path in known:
                self.document_session_documents[known[item_path]] = item
            else:
                known[item_path] = len(self.document_session_documents)
                self.document_session_documents.append(item)
        effective_paths = list(self.document_session_documents)
        self.document_documents = effective_paths
        model_path=self.config.get("llama_server",{}).get("model",""); model_name=os.path.basename(model_path) or "local-model"
        history=list(self.document_history)
        self.document_thread=DocumentAnalysisThread(
            self.config["api_url"], model_name, effective_paths, question, self,
            audio_data=audio_data,
            history=history,
            skill_manager=self.skill_manager,
        )
        self.document_thread.new_text.connect(self.update_document_text)
        self.document_thread.tool_event.connect(self.update_document_tool_event)
        self.document_thread.request_error.connect(self.handle_document_error)
        self.document_thread.finished.connect(self.on_document_finished)
        self.document_thread.start()

    @staticmethod
    def _format_tool_event(phase, name, detail):
        """Formate un événement d'outil lisible dans le flux de conversation."""
        icons = {"appel": "🔧", "résultat": "✅", "erreur": "❌"}
        icon = icons.get(phase, "🔧")
        title = f"{icon} Outil {phase} : `{name}`"
        detail = (detail or "").strip()
        if not detail:
            return f"\n\n{title}\n\n"
        # Protection contre un résultat binaire ou anormalement volumineux.
        if len(detail) > 12000:
            detail = detail[:12000] + "\n… [détail tronqué dans l'interface]"
        return f"\n\n{title}\n```json\n{detail}\n```\n\n"

    def update_document_tool_event(self, phase, name, detail):
        if self.document_dialog is None:
            return
        if phase == "appel":
            self.document_dialog.status.setText(f"Utilisation de l’outil : {name}")
            self.document_dialog.status.show()
            self.document_dialog._update_height()
            return
        self.document_dialog.status.clear()
        self.document_dialog.status.hide()
        self.document_dialog._update_height()
        if phase == "résultat":
            for path in self._created_file_paths(detail):
                self.update_document_text(self._file_link_markdown(path))

    def update_document_text(self, text):
        self.response_text += text
        if self.document_dialog is not None: self.document_dialog.append_response(text)

    def open_document_source(self, filename, page):
        """Ouvre le document demandé par un lien de source, à la bonne page."""
        decoded_name = filename.strip().lstrip("-•* ").strip()
        requested_name = os.path.basename(decoded_name).casefold()
        for document in self.document_documents:
            path = document.get("path") if isinstance(document, dict) else document
            if os.path.basename(path).casefold() == requested_name:
                try:
                    _open_pdf_at_page(path, int(page))
                except Exception:
                    LOGGER.exception("Impossible d'ouvrir la source demandée")
                return

    def _open_first_cited_pdf(self, answer):
        """Ouvre le premier PDF réellement cité dans la réponse, à la bonne page."""
        matches = re.findall(r"(?:Source\s*:\s*)?([^\n()]+?\.pdf)\s*[—-]\s*(?:p(?:age)?\.?\s*)?(\d+)", answer, re.IGNORECASE)
        if not matches:
            return
        by_name = {}
        for document in self.document_documents:
            path = document.get("path") if isinstance(document, dict) else document
            by_name[os.path.basename(path).lower()] = path
        for filename, page in matches:
            path = by_name.get(os.path.basename(filename.strip()).lower())
            if path:
                try: _open_pdf_at_page(path, int(page))
                except Exception: LOGGER.exception("Impossible d'ouvrir le PDF cité")
                return

    def handle_document_error(self, message, _incompatible):
        self.request_failed=True; self.document_response_active=False
        if self.document_dialog is not None: self.document_dialog.show_error(message)


    def on_document_finished(self):
        thread=self.sender()
        if thread is not self.document_thread:
            if thread is not None: thread.deleteLater()
            return
        self.document_source_pages=list(thread.source_pages); self.document_thread=None; self.document_response_active=False; thread.deleteLater()
        if self.document_dialog is not None:
            _, answer = self.split_thinking_and_answer(self.response_text)
            if answer.strip():
                # L'historique est envoyé à la prochaine question afin de permettre les suivis.
                self.document_history.append({"role": "user", "content": self.document_dialog.turns[-1].get("question", "")})
                self.document_history.append({"role": "assistant", "content": answer.strip()})
            self.document_dialog.finish_response()
            if self.document_documents:
                self.document_dialog.show_source_captures(answer, self.document_documents)
        # Les documents ne sont jamais ouverts automatiquement. Les liens de la
        # section Sources permettent de les ouvrir volontairement à la bonne page.


    def set_hotkeys_enabled(self, enabled, persist=True):
        """Active ou désactive tous les raccourcis globaux de l'assistant."""
        enabled = bool(enabled)
        app = QApplication.instance()
        menu_manager = getattr(app, "menu_hotkey_manager", None)
        numeric_manager = getattr(app, "numeric_hotkey_manager", None)
        voice_manager = getattr(app, "voice_hotkey_manager", None)

        if menu_manager is not None:
            menu_manager.set_enabled(enabled)
        if numeric_manager is not None:
            numeric_manager.set_enabled(enabled)
        if voice_manager is not None:
            voice_enabled = bool(self.config.get("voice_input", {}).get("enabled", True))
            voice_manager.set_enabled(enabled and voice_enabled)

        self.config["hotkeys_enabled"] = enabled
        if persist:
            save_config(self.config)

        tray_action = getattr(app, "hotkeys_action", None)
        if tray_action is not None:
            tray_action.setText(
                "Désactiver les raccourcis" if enabled
                else "Activer les raccourcis"
            )

        state = "activés" if enabled else "désactivés"
        tray_icon = getattr(app, "tray_icon", None)
        if tray_icon is not None:
            tray_icon.setToolTip(f"Assistant IA - Raccourcis {state}")
        LOGGER.info("Raccourcis clavier %s.", state)

    def toggle_hotkeys(self, enabled=None):
        """Inverse l'état des raccourcis ou applique l'état fourni par Qt."""
        if enabled is None:
            enabled = not bool(self.config.get("hotkeys_enabled", True))
        self.set_hotkeys_enabled(enabled)

    def set_automatic_reading_enabled(self, enabled, persist=True):
        """Active ou désactive la lecture automatique des réponses."""
        enabled = bool(enabled)
        tts_config = self.config.setdefault(
            "text_to_speech", copy.deepcopy(DEFAULT_CONFIG["text_to_speech"])
        )
        tts_config["automatic_reading"] = enabled
        if persist:
            save_config(self.config)

        app = QApplication.instance()
        tray_action = getattr(app, "automatic_reading_action", None)
        if tray_action is not None:
            tray_action.setText(
                "Désactiver la lecture à voix haute" if enabled
                else "Activer la lecture à voix haute"
            )

        if not enabled:
            self.stop_speech()

        state = "activée" if enabled else "désactivée"
        LOGGER.info("Lecture automatique des réponses %s.", state)

    def toggle_automatic_reading(self):
        """Inverse la lecture automatique depuis l'icône système."""
        current = self._automatic_tts_enabled()
        self.set_automatic_reading_enabled(not current)

    def quit_application(self):
        self.stop_generation()
        LLAMA_SERVER_MANAGER.stop()
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

    def open_settings(self):
        self.cancel_voice_operation()
        manager = getattr(QApplication.instance(), "voice_hotkey_manager", None)
        if manager is not None: manager.set_enabled(False)
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_():
            self.config = load_config()
            self.set_automatic_reading_enabled(
                self._automatic_tts_enabled(), persist=False
            )
            self.label.setText("Paramètres mis à jour.")
            self.show_window()
        if manager is not None:
            manager.set_enabled(
                bool(self.config.get("hotkeys_enabled", True))
                and bool(self.config.get("voice_input", {}).get("enabled", True))
            )

    def update_window_title(self):
        title = re.sub(r"\s+", " ", self.selected_text).strip() if self.selected_text else ""
        self.title_label.setText(title or "…")
        self.title_label.setToolTip(title)

    parse_audio_response = staticmethod(parse_audio_response)
    format_inline_markdown = staticmethod(format_inline_markdown)
    markdown_to_html = staticmethod(markdown_to_html)
    split_thinking_and_answer = staticmethod(split_thinking_and_answer)


    def render_response(self, status_text=""):
        if status_text:
            content = (
                '<div style="color:#555555; font-style:italic;">'
                f'{html.escape(status_text)}'
                '</div>'
            )
        else:
            _, answer_text = self.split_thinking_and_answer(self.response_text)
            if self.current_request_is_audio:
                transcript, answer_text = self.parse_audio_response(answer_text)
                if transcript:
                    self.title_label.setText(transcript)
                    self.title_label.setToolTip(transcript)
            elif self.document_response_active:
                self.title_label.setText("Documents")
                self.title_label.setToolTip("Analyse documentaire")
            content = self.markdown_to_html(answer_text) if answer_text else ''

        logo_html = ""
        logo_path = "logo.png"
        if hasattr(sys, 'frozen'):
            logo_path = os.path.join(sys._MEIPASS, "logo.png")
        elif '__file__' in globals():
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

        if os.path.exists(logo_path) and not status_text:
            abs_path = os.path.abspath(logo_path).replace('\\', '/')
            logo_html = f'<img src="file:///{abs_path}" width="32" height="32" />'
            final_html = f'<table cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td valign="top" style="padding-right: 8px; padding-bottom: 4px;">{logo_html}</td><td valign="top" width="100%">{content}</td></tr></table>'
        else:
            final_html = content

        self.label.setText(final_html)

    def update_loading_animation(self):
        self.loading_dot_count = (self.loading_dot_count % 3) + 1
        dots = "." * self.loading_dot_count
        self.render_response(f"{self.loading_action_name}{dots}")

    def stop_generation(self):
        self.loading_timer.stop()
        if self.document_thread is not None and self.document_thread.isRunning():
            self.document_thread.stop()
        thread = self.thread
        self.thread = None
        if thread is not None and thread.isRunning():
            thread.stop()
            try:
                thread.new_text.disconnect(self.update_text)
                thread.finished.disconnect(self.on_finished)
            except (TypeError, RuntimeError):
                pass
            thread.finished.connect(thread.deleteLater)

    def close_response_window(self):
        self.stop_generation()
        self.stop_speech()
        self.hide()

    def animate_copy_button(self):
        """Remplace brièvement l'icône Copier par une coche, puis la restaure."""
        self.copy_animation_id = getattr(self, "copy_animation_id", 0) + 1
        animation_id = self.copy_animation_id

        if hasattr(self, "copy_animation"):
            self.copy_animation.stop()

        def animate_icon_size(start_size, end_size, duration, on_finished=None):
            if animation_id != self.copy_animation_id:
                return
            self.copy_animation = QPropertyAnimation(self.copy_button, b"iconSize", self)
            self.copy_animation.setDuration(duration)
            self.copy_animation.setStartValue(start_size)
            self.copy_animation.setEndValue(end_size)
            self.copy_animation.setEasingCurve(QEasingCurve.InOutCubic)
            if on_finished is not None:
                self.copy_animation.finished.connect(on_finished)
            self.copy_animation.start()

        def show_check():
            if animation_id != self.copy_animation_id:
                return
            self.copy_button.setIcon(ICONS_DARK["check"])
            animate_icon_size(QSize(8, 8), QSize(17, 17), 160, schedule_restore)

        def schedule_restore():
            QTimer.singleShot(1100, restore_copy)

        def restore_copy():
            if animation_id != self.copy_animation_id:
                return

            def show_copy():
                if animation_id != self.copy_animation_id:
                    return
                self.copy_button.setIcon(ICONS_DARK["copy"])
                animate_icon_size(QSize(8, 8), QSize(17, 17), 160)

            animate_icon_size(QSize(17, 17), QSize(8, 8), 120, show_copy)

        animate_icon_size(QSize(17, 17), QSize(8, 8), 120, show_check)

    def toggle_speech(self):
        if self.tts_thread is not None and self.tts_thread.isRunning():
            self.stop_speech()
            return
        _, answer_text = self.split_thinking_and_answer(self.response_text)
        if self.current_request_is_audio:
            _, answer_text = self.parse_audio_response(answer_text)
        answer_text = answer_text.strip()
        if not answer_text:
            self.speak_button.setToolTip("Aucune réponse à lire")
            return
        cfg = self.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
        self.tts_thread = KokoroTtsThread(answer_text, cfg, self)
        self.tts_thread.finished_ok.connect(self.on_speech_finished)
        self.tts_thread.failed.connect(self.on_speech_failed)
        self.tts_thread.finished.connect(self.tts_thread.deleteLater)
        self.speak_button.setIcon(ICONS_DARK["stop"])
        self.speak_button.setToolTip("Arrêter la lecture")
        self.tts_thread.start()

    def _automatic_tts_enabled(self):
        return bool(
            self.config.get("text_to_speech", {}).get("automatic_reading", False)
        )

    def queue_streaming_speech(self, text, flush=False):
        """Découpe le flux en phrases et les envoie immédiatement à Kokoro."""
        if not self._automatic_tts_enabled() or self.current_request_is_audio:
            return

        self.tts_streaming_auto = True
        self.tts_stream_buffer += text

        # Coupe après une ponctuation forte. La limite de 24 caractères évite
        # de lancer Kokoro sur de très petits fragments ou des titres isolés.
        while True:
            match = re.search(r"[.!?…](?:\s+|$)", self.tts_stream_buffer)
            if match is None:
                break
            end = match.end()
            segment = self.tts_stream_buffer[:end].strip()
            if len(markdown_to_spoken_text(segment)) < 24 and not flush:
                next_match = re.search(r"[.!?…](?:\s+|$)", self.tts_stream_buffer[end:])
                if next_match is None:
                    break
                end += next_match.end()
                segment = self.tts_stream_buffer[:end].strip()
            self.tts_stream_buffer = self.tts_stream_buffer[end:].lstrip()
            if markdown_to_spoken_text(segment):
                self.tts_queue.append(segment)

        if flush:
            remaining = self.tts_stream_buffer.strip()
            self.tts_stream_buffer = ""
            if markdown_to_spoken_text(remaining):
                self.tts_queue.append(remaining)

        self._start_next_tts_segment()

    def _start_next_tts_segment(self):
        if self.tts_thread is not None or not self.tts_queue:
            if self.tts_thread is None and not self.tts_queue and not self.is_generating:
                self.tts_streaming_auto = False
                self.speak_button.setIcon(ICONS_DARK["speak"])
                self.speak_button.setToolTip("Lire la réponse à haute voix")
            return

        segment = self.tts_queue.pop(0)
        cfg = self.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
        thread = KokoroTtsThread(segment, cfg, self)
        self.tts_thread = thread
        thread.finished_ok.connect(self._on_tts_segment_finished)
        thread.failed.connect(self.on_speech_failed)
        thread.finished.connect(thread.deleteLater)
        self.speak_button.setIcon(ICONS_DARK["stop"])
        self.speak_button.setToolTip("Arrêter la lecture")
        thread.start()

    def _on_tts_segment_finished(self):
        self.tts_thread = None
        QTimer.singleShot(0, self._start_next_tts_segment)

    def stop_speech(self):
        self.tts_queue.clear()
        self.tts_stream_buffer = ""
        self.tts_streaming_auto = False
        if self.tts_thread is not None:
            self.tts_thread.stop()
        self.on_speech_finished()

    def on_speech_finished(self):
        self.speak_button.setIcon(ICONS_DARK["speak"])
        self.speak_button.setToolTip("Lire la réponse à haute voix")
        self.tts_thread = None

    def on_speech_failed(self, detail):
        LOGGER.error("Échec de la synthèse vocale Kokoro : %s", detail)
        self.tts_queue.clear()
        self.tts_stream_buffer = ""
        self.tts_streaming_auto = False
        self.speak_button.setIcon(ICONS_DARK["speak"])
        self.speak_button.setToolTip("Synthèse vocale indisponible : " + detail[:120])
        self.tts_thread = None

    def open_response_link(self, href):
        """Ouvre explicitement les fichiers locaux avec l'application Windows associée."""
        try:
            url = QUrl(str(href))
            if url.scheme().lower() == "file":
                local_path = url.toLocalFile()
                if local_path and os.path.isfile(local_path):
                    if sys.platform == "win32":
                        os.startfile(local_path)
                    else:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(local_path))
                    return
                LOGGER.warning("Fichier lié introuvable : %s", local_path)
                return
            QDesktopServices.openUrl(url)
        except Exception:
            LOGGER.exception("Impossible d'ouvrir le lien : %s", href)

    def copy_response(self):
        _, answer_text = self.split_thinking_and_answer(self.response_text)
        if self.current_request_is_audio:
            _, answer_text = self.parse_audio_response(answer_text)
        if answer_text:
            try:
                pyperclip.copy(answer_text)
            except pyperclip.PyperclipException:
                self.copy_button.setToolTip("Presse-papiers indisponible")
                return
            self.animate_copy_button()
            self.copy_button.setToolTip("Réponse copiée")
            QTimer.singleShot(1500, lambda: self.copy_button.setToolTip("Copier la réponse"))

    def _selected_voice_device(self):
        voice = self.config.get("voice_input", {})
        saved_name = voice.get("input_device_name", "")
        try:
            devices = sd.query_devices()
            if saved_name:
                for index, device in enumerate(devices):
                    if device.get("name") == saved_name and int(device.get("max_input_channels", 0)) > 0:
                        return index
                LOGGER.warning("Microphone enregistré introuvable, périphérique par défaut utilisé")
            return None
        except Exception:
            return voice.get("input_device")

    def start_voice_recording(self, index):
        """Ctrl+Alt+N démarre une capture destinée exclusivement à l'action N."""
        voice = self.config.get("voice_input", {})
        if not 0 <= index < len(self.config["actions"]):
            return
        if not voice.get("enabled", True) or self.voice_sending or (self.audio_thread is not None and self.audio_thread.isRunning()):
            return
        self.voice_action_index = index
        self.voice_cancelled = False
        self.recording_indicator.start_recording(self.config["actions"][index]["name"])
        self.audio_thread = AudioRecorderThread(
            self._selected_voice_device(),
            voice.get("sample_rate", 16000),
            voice.get("maximum_duration", 60.0),
            release_tail_ms=voice.get("release_tail_ms", 700),
            microphone_gain=voice.get("microphone_gain", 2.0),
            parent=self,
        )
        self.audio_thread.level_changed.connect(self.recording_indicator.set_level)
        self.audio_thread.recorded.connect(self.handle_voice_audio)
        self.audio_thread.error.connect(self.handle_voice_error)
        self.audio_thread.maximum_reached.connect(lambda: self.recording_indicator.set_status("Durée maximale atteinte"))
        self.audio_thread.start()

    def stop_voice_recording(self, index):
        if self.voice_action_index != index:
            return
        if self.audio_thread is not None and self.audio_thread.isRunning():
            self.recording_indicator.hide()
            self.audio_thread.stop_recording()


    def cancel_voice_operation(self):
        self.voice_cancelled = True
        self.voice_action_index = None
        if self.audio_thread is not None and self.audio_thread.isRunning(): self.audio_thread.stop_recording()
        if self.voice_sending: self.stop_generation()
        self.voice_sending = False
        self.recording_indicator.hide()

    def handle_voice_audio(self, audio_data, duration, rms):
        self.audio_thread = None
        if self.voice_cancelled: return
        voice = self.config.get("voice_input", {})
        if not audio_data or duration < voice.get("minimum_duration",0.3) or rms < voice.get("minimum_rms_level", 0.0001):
            self.recording_indicator.set_status("Aucun son détecté")
            QTimer.singleShot(1200, self.recording_indicator.hide)
            return
        if len(audio_data) > 25 * 1024 * 1024:
            self.handle_voice_error("L’enregistrement audio est trop volumineux."); return
        # L'indicateur disparaît pendant l'envoi, sans afficher « Envoi au modèle ».
        self.recording_indicator.hide()
        self.voice_sending = True
        action_index = self.voice_action_index
        self.voice_action_index = None
        if action_index is not None:
            self.trigger_action(action_index, audio_data=audio_data, audio_format="wav")

    def handle_voice_error(self, message):
        self.audio_thread = None; self.voice_sending = False; self.voice_action_index = None
        self.recording_indicator.hide()
        self.label.setText(f"⚠️ {html.escape(message)}"); self.show_window()

    def trigger_action(self, index, user_text_override=None, audio_data=None, audio_format=None):
        if not 0 <= index < len(self.config["actions"]): return
        if audio_data is not None:
            self.selected_text = ""
            self.execute_action(self.config["actions"][index], audio_data=audio_data, audio_format=audio_format)
            return
        self.selected_text = user_text_override if user_text_override is not None else self.get_selected_text()
        self.execute_action(self.config["actions"][index])

    def execute_action(self, action_cfg, preserve_position=False, audio_data=None, audio_format=None):
        self.stop_generation()
        self.stop_speech()
        self.last_action_cfg = action_cfg.copy()
        self.current_request_is_audio = audio_data is not None
        self.update_window_title()
        if audio_data is None and not self.selected_text:
            self.label.setText("⚠️ Aucun texte sélectionné.")
            self.show_window()
            return
        self.response_text = ""
        self.request_failed = False
        self.pending_stream_text = ""
        self.stream_render_timer.stop()
        self.loading_action_name = action_cfg['name']
        self.loading_dot_count = 0
        self.is_generating = True
        self.update_loading_animation()
        self.loading_timer.start()
        self.show_window(preserve_position=preserve_position)
        # Hauteur fixée une seule fois avant le premier token. La QScrollArea
        # absorbe ensuite la croissance du texte sans redessiner la fenêtre native.
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        stable_height = min(max(180, self.height()), max(180, int(screen.availableGeometry().height() * 0.45)))
        self.resize(self.width(), stable_height)
        self.expanded_height = stable_height
        model_path = self.config.get("llama_server", {}).get("model", "")
        model_name = os.path.basename(model_path) or "local-model"
        self.thread = LlamaThread(
            self.config["api_url"],
            self.selected_text,
            action_cfg["system_prompt"],
            action_cfg["prompt_prefix"],
            model_name,
            audio_data=audio_data,
            audio_format=audio_format,
            audio_language=self.config.get("voice_input", {}).get("language", "fr"),
            vocabulary_prompt=self.config.get("voice_input", {}).get("vocabulary_prompt", ""),
            skill_manager=self.skill_manager,
            enable_tools=(str(action_cfg.get("name", "")).strip().casefold() != "améliorer"),
        )
        self.thread.new_text.connect(self.update_text)
        self.thread.tool_event.connect(self.update_tool_event)
        self.thread.new_text.connect(lambda _text: self.recording_indicator.hide())
        self.thread.request_error.connect(self.handle_voice_request_error)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def handle_voice_request_error(self, message, incompatible):
        self.request_failed = True
        self.voice_sending = False
        self.recording_indicator.hide()
        self.label.setText(f"⚠️ {html.escape(message)}")
        self.show_window()

    def show_window(self, preserve_position=False):
        previous_position = self.pos()
        self.stop_height_animation()
        self.separator_container.show()
        self.scroll_area.show()
        self.is_collapsed = False

        # Applique toujours la hauteur calculée. Une comparaison avec la hauteur
        # courante conservait parfois une géométrie intermédiaire trop petite.
        self.expanded_height = self.calculate_expanded_height()
        self.resize(self.width(), self.expanded_height)

        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        x = cursor_pos.x()
        y = cursor_pos.y() + 20
        if x + self.width() > screen_rect.right() - 10: x = screen_rect.right() - self.width() - 10
        if x < screen_rect.left() + 10: x = screen_rect.left() + 10
        if y + self.height() > screen_rect.bottom() - 10: y = cursor_pos.y() - self.height() - 20
        if y < screen_rect.top() + 10: y = screen_rect.top() + 10
        if preserve_position and self.isVisible():
            self.move(previous_position)
        else:
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _created_file_paths(detail):
        """Extrait les chemins de fichiers existants d'un résultat de skill."""
        try:
            payload = json.loads(detail or "null")
        except (json.JSONDecodeError, TypeError):
            payload = detail
        values = []
        def visit(value):
            if isinstance(value, dict):
                for child in value.values(): visit(child)
            elif isinstance(value, (list, tuple, set)):
                for child in value: visit(child)
            elif isinstance(value, str):
                values.append(value.strip())
        visit(payload)
        extensions = {".docx", ".pdf", ".xlsx", ".xls", ".pptx", ".csv", ".txt"}
        found = []
        for value in values:
            if not value or Path(value).suffix.lower() not in extensions:
                continue
            candidate = os.path.expandvars(os.path.expanduser(value))
            if not os.path.isabs(candidate):
                candidate = os.path.join(APP_DIR, candidate)
            candidate = os.path.normpath(candidate)
            if os.path.isfile(candidate) and candidate not in found:
                found.append(candidate)
        return found

    @staticmethod
    def _file_link_markdown(path):
        # Masque uniquement l'extension dans le libellé affiché.
        # Le lien file:/// conserve le nom réel complet afin de rester ouvrable.
        display_name = Path(path).stem
        return f"📄 [{display_name}]({Path(path).resolve().as_uri()})\n"

    def update_tool_event(self, phase, name, detail):
        """Affiche seulement le nom de l'outil, uniquement pendant son exécution."""
        if phase == "appel":
            if self.loading_timer.isActive():
                self.loading_timer.stop()
            self._title_before_tool = self.title_label.text()
            self.title_label.setText(f"Outil : {name}")
            self.title_label.setToolTip(f"Utilisation de l’outil : {name}")
            return
        previous_title = getattr(self, "_title_before_tool", "")
        if previous_title:
            self.title_label.setText(previous_title)
            self.title_label.setToolTip(previous_title)
        self._title_before_tool = ""
        if phase == "résultat":
            for path in self._created_file_paths(detail):
                self.pending_stream_text += self._file_link_markdown(path)
            if self.pending_stream_text and not self.stream_render_timer.isActive():
                self.stream_render_timer.start()

    def update_text(self, text):
        # Le premier fragment doit stopper immediatement l'indicateur d'attente.
        if self.loading_timer.isActive():
            self.loading_timer.stop()
        self.pending_stream_text += text
        self.queue_streaming_speech(text)
        if not self.stream_render_timer.isActive():
            self.stream_render_timer.start()

    def flush_stream_text(self):
        if not self.pending_stream_text:
            return
        self.response_text += self.pending_stream_text
        self.pending_stream_text = ""
        # Méthode de streaming issue de Assistant_streamok.py : rendu rapide,
        # ajustement immédiat du contenu et de la hauteur à chaque lot de tokens.
        self.render_response()
        self.label.adjustSize()
        if not self.is_collapsed:
            self.stop_height_animation()
            self.expanded_height = self.calculate_expanded_height()
            self.resize(self.width(), self.expanded_height)
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_finished(self):
        finished_thread = self.sender()
        if finished_thread is not self.thread:
            if finished_thread is not None:
                finished_thread.deleteLater()
            return
        self.loading_timer.stop()
        self.stream_render_timer.stop()
        self.flush_stream_text()
        self.tool_status_label.hide()
        self.tool_status_label.clear()
        previous_title = getattr(self, "_title_before_tool", "")
        if previous_title:
            self.title_label.setText(previous_title)
            self.title_label.setToolTip(previous_title)
        self._title_before_tool = ""
        if not self.is_collapsed:
            final_height = self.calculate_expanded_height()
            self.expanded_height = final_height
            self.resize(self.width(), final_height)
        self.is_generating = False
        self.voice_sending = False
        self.recording_indicator.hide()
        self.thread = None
        finished_thread.deleteLater()
        if not self.response_text.strip() and not self.request_failed:
            self.render_response("Aucune réponse reçue.")
        elif not self.request_failed and self._automatic_tts_enabled():
            if self.current_request_is_audio:
                # Les requêtes Ctrl+Alt+N sont volontairement exclues de la
                # lecture en streaming afin de ne pas lire la transcription ou
                # les fragments techniques. Une fois la réponse complète, on
                # lance toutefois la lecture automatique du texte nettoyé.
                QTimer.singleShot(0, self.toggle_speech)
            else:
                # Termine le dernier fragment sans attendre une ponctuation finale.
                self.queue_streaming_speech("", flush=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.stop_height_animation()
        self.is_collapsed = False
        self.separator_container.show()
        self.scroll_area.show()
        self.expanded_height = self.calculate_expanded_height()
        self.resize(self.width(), self.expanded_height)
        self.update_rounded_mask()
        QTimer.singleShot(0, self.apply_native_window_effects)

    def apply_native_window_effects(self):
        hwnd = int(self.winId())
        apply_acrylic_blur(hwnd, 0xB8F5F5F5)
        apply_rounded_corners(hwnd)
        self.update_rounded_mask()
        QTimer.singleShot(0, self.update_rounded_mask)

# ==========================================
# RACCOURCI D'OUVERTURE DU MENU
# ==========================================
class MenuHotkeyManager:
    """Gère proprement l'enregistrement de Ctrl+. sans toucher aux autres hooks."""

    def __init__(self, assistant):
        self.assistant = assistant
        self.handle = None
        self.enabled = False
        self.set_enabled(True)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self.handle = keyboard.add_hotkey(
                "ctrl+.", self.assistant.show_menu_signal.emit, suppress=False
            )
        elif self.handle is not None:
            # Le raccourci peut avoir deja ete retire par un nettoyage global.
            # Dans ce cas, keyboard.remove_hotkey leve ValueError/KeyError.
            try:
                keyboard.remove_hotkey(self.handle)
            except (KeyError, ValueError):
                pass
            finally:
                self.handle = None

    def stop(self):
        self.set_enabled(False)


# ==========================================
# RACCOURCIS NUMÉRIQUES AVEC SUPPRESSION CONDITIONNELLE
# ==========================================
class NumericHotkeyManager:
    """Gère Ctrl+0 à Ctrl+9 en neutralisant le zoom d'Adobe Reader/Acrobat.

    Par défaut, ces combinaisons sont transmises normalement au système
    (suppress=False) afin de ne pas gêner les autres applications. Dès que
    Adobe Reader ou Acrobat passe au premier plan, les raccourcis sont
    ré-enregistrés avec suppress=True : ils déclenchent uniquement les
    actions de l'assistant et n'atteignent plus Adobe, qui ne peut donc
    plus interpréter Ctrl+0..9 comme des raccourcis de zoom.
    """

    POLL_INTERVAL_MS = 250

    def __init__(self, assistant, parent=None):
        self.assistant = assistant
        self.enabled = True
        self.suppressed = None  # Force un premier enregistrement.
        self.timer = QTimer(parent)
        self.timer.setInterval(self.POLL_INTERVAL_MS)
        self.timer.timeout.connect(self._poll_foreground_app)
        self._register(suppress=False)
        self.timer.start()

    def _make_callback(self, index):
        if index < 0:
            # Ctrl+0 replie ou déplie la fenêtre visible, comme un clic sur sa barre de titre.
            return self.assistant.toggle_collapse_signal.emit
        return lambda: self.assistant.trigger_direct_signal.emit(index)

    def _register(self, suppress):
        self._unregister()
        self.suppressed = suppress
        for i in range(0, 10):
            # Ctrl+9 est réservé à l'analyse documentaire : il est toujours
            # supprimé du logiciel au premier plan pour éviter, par exemple,
            # le raccourci Ctrl+9 d'un navigateur ou d'un autre logiciel.
            effective_suppress = True if i == 9 else suppress
            keyboard.add_hotkey(
                f'ctrl+{i}',
                self._make_callback(i - 1),
                suppress=effective_suppress
            )

    def _unregister(self):
        for i in range(0, 10):
            try:
                keyboard.remove_hotkey(f'ctrl+{i}')
            except (KeyError, ValueError):
                pass

    def _poll_foreground_app(self):
        if not self.enabled:
            return
        should_suppress = is_adobe_reader_foreground()
        if should_suppress != self.suppressed:
            self._register(suppress=should_suppress)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self.suppressed = None
            self._register(suppress=is_adobe_reader_foreground())
            self.timer.start()
        else:
            self.timer.stop()
            self._unregister()
            self.suppressed = None

    def stop(self):
        self.timer.stop()
        self._unregister()


# ==========================================
# ICÔNE DE LA ZONE DE NOTIFICATION WINDOWS
# ==========================================
def create_tray_icon(app, assistant):
    """Crée l'icône près de l'horloge Windows.

    Un clic gauche sur l'icône n'ouvre aucune fenêtre.
    Le clic droit propose Afficher, Paramètres et Quitter.
    """
    tray_icon = QSystemTrayIcon(app)

    # Logo fourni avec l'application, inspiré de la pièce jointe.
    # Le chemin reste valide même si l'application est lancée depuis un autre dossier.
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "assistant_icon.webp"
    )
    icon = QIcon(icon_path)
    if icon.isNull():
        # Icône de secours si le fichier visuel est absent.
        fallback_svg = (
            '<path d="M12 1.5C11.2 7.5 7.5 11.2 1.5 12 '
            'C7.5 12.8 11.2 16.5 12 22.5 '
            'C12.8 16.5 16.5 12.8 22.5 12 '
            'C16.5 11.2 12.8 7.5 12 1.5z"/>'
        )
        icon = create_svg_icon(fallback_svg, "#FFFFFF")
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)

    app.setWindowIcon(icon)
    tray_icon.setIcon(icon)
    tray_icon.setToolTip("Assistant IA")

    tray_menu = QMenu()
    tray_menu.setObjectName("TrayLightMenu")
    tray_menu.setAttribute(Qt.WA_TranslucentBackground, False)
    tray_menu.setAutoFillBackground(True)
    tray_menu.setStyleSheet("""
        QMenu#TrayLightMenu {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 6px;
            font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
            font-size: 13px;
        }
        QMenu#TrayLightMenu::item {
            background: transparent;
            color: #111111;
            padding: 7px 24px 7px 12px;
            margin: 1px;
            border-radius: 5px;
        }
        QMenu#TrayLightMenu::item:selected {
            background-color: #DCEBFF;
            color: #111111;
        }
        QMenu#TrayLightMenu::separator {
            height: 1px;
            background-color: #D7E0EA;
            margin: 5px 8px;
        }
    """)
    settings_action = QAction("Paramètres", tray_menu)
    hotkeys_enabled = bool(assistant.config.get("hotkeys_enabled", True))
    hotkeys_action = QAction(
        "Désactiver les raccourcis" if hotkeys_enabled
        else "Activer les raccourcis",
        tray_menu,
    )
    automatic_reading_enabled = bool(
        assistant.config.get("text_to_speech", {}).get("automatic_reading", False)
    )
    automatic_reading_action = QAction(
        "Désactiver la lecture à voix haute" if automatic_reading_enabled
        else "Activer la lecture à voix haute",
        tray_menu,
    )
    quit_action = QAction("Quitter", tray_menu)

    settings_action.triggered.connect(assistant.open_settings)
    hotkeys_action.triggered.connect(lambda: assistant.toggle_hotkeys())
    automatic_reading_action.triggered.connect(assistant.toggle_automatic_reading)
    app.hotkeys_action = hotkeys_action
    app.automatic_reading_action = automatic_reading_action
    quit_action.triggered.connect(assistant.quit_application)

    tray_menu.addAction(settings_action)
    tray_menu.addAction(hotkeys_action)
    tray_menu.addAction(automatic_reading_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)
    tray_icon.setContextMenu(tray_menu)

    def handle_tray_activation(reason):
        # Trigger correspond au clic gauche simple dans QSystemTrayIcon.
        if reason == QSystemTrayIcon.Trigger:
            assistant.show_runtime_information()

    tray_icon.activated.connect(handle_tray_activation)
    tray_icon.show()
    return tray_icon

# ==========================================
# THÈME CLAIR DES MENUS QT
# ==========================================
def apply_light_popup_theme(app):
    """Force les menus Qt, y compris Copier/Coller, en thème clair.

    Les menus contextuels standards de QTextEdit/QTextBrowser sont créés par Qt
    au moment du clic droit. Un style local sur la fenêtre ne suffit donc pas :
    la palette et le QSS doivent être appliqués au niveau de QApplication.
    """
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor("#F8FAFC"))
    palette.setColor(QPalette.WindowText, QColor("#111111"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F1F5F9"))
    palette.setColor(QPalette.Text, QColor("#111111"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#111111"))
    palette.setColor(QPalette.Highlight, QColor("#DCEBFF"))
    palette.setColor(QPalette.HighlightedText, QColor("#111111"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#111111"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#8A949F"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#8A949F"))
    app.setPalette(palette)
    app.setStyleSheet((app.styleSheet() or "") + """
        QMenu {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 5px;
            font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
            font-size: 12px;
        }
        QMenu::item {
            background-color: transparent;
            color: #111111;
            min-height: 20px;
            padding: 6px 28px 6px 10px;
            margin: 1px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #DCEBFF;
            color: #111111;
        }
        QMenu::item:disabled {
            color: #8A949F;
            background-color: transparent;
        }
        QMenu::separator {
            height: 1px;
            background-color: #D7E0EA;
            margin: 5px 8px;
        }
        QMenu::icon { padding-left: 4px; }
        QToolTip {
            background-color: #FFFFFF;
            color: #111111;
            border: 1px solid #CBD7E4;
            padding: 4px 7px;
        }
    """)

# ==========================================
# POINT D'ENTRÉE
# ==========================================
def main() -> int:
    """Initialise l'application et retourne son code de sortie."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if sys.platform == 'win32':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Assistant.IA')
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    apply_light_popup_theme(app)
    app.setApplicationName("Assistant IA")
    app.setApplicationDisplayName("Assistant IA")
    app.setQuitOnLastWindowClosed(False)

    initialize_icons()
    assistant = AssistantWindow()
    app.aboutToQuit.connect(LLAMA_SERVER_MANAGER.stop)

    if QSystemTrayIcon.isSystemTrayAvailable():
        # Conserver une référence empêche Python de détruire l'icône.
        app.tray_icon = create_tray_icon(app, assistant)
        assistant.start_server_online_notification(app.tray_icon)
    else:
        LOGGER.warning("Zone de notification Windows indisponible.")

    # Les trois familles de raccourcis sont pilotées depuis l'icône système.
    app.menu_hotkey_manager = MenuHotkeyManager(assistant)

    # Ctrl+0 à Ctrl+9 : suppression automatique du zoom Adobe Reader/Acrobat
    # lorsque ces applications sont au premier plan, sinon comportement normal
    # (les raccourcis Ctrl+1 à Ctrl+9 de l'assistant restent toujours actifs).
    app.numeric_hotkey_manager = NumericHotkeyManager(assistant, app)
    app.voice_hotkey_manager = VoiceHotkeyManager(assistant)
    assistant.set_hotkeys_enabled(
        bool(assistant.config.get("hotkeys_enabled", True)), persist=False
    )
    app.aboutToQuit.connect(app.menu_hotkey_manager.stop)
    app.aboutToQuit.connect(app.voice_hotkey_manager.stop)
    app.aboutToQuit.connect(app.numeric_hotkey_manager.stop)

    LOGGER.info("Assistant prêt.")
    LOGGER.info("Sélectionnez du texte et appuyez sur Ctrl+. (menu) ou Ctrl+1 à Ctrl+9 (direct).")

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
