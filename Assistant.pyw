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
# CONFIGURATION WINDOWS 11 ACRYLIC BLUR & THÈME
# ==========================================
from src.ui.theme import (
    AccentPolicy,
    WindowCompositionAttributeData,
    apply_acrylic_blur,
    apply_rounded_corners,
    apply_light_popup_theme,
)
from src.platform.foreground import (
    ADOBE_PROCESS_NAMES,
    get_foreground_process_name,
    is_adobe_reader_foreground,
)
from src.ui.icons import (
    create_svg_icon,
    ICONS,
    ICONS_DARK,
    initialize_icons,
)

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
from src.llm.server_manager import LlamaServerManager, get_server_manager

LLAMA_SERVER_MANAGER = get_server_manager()


# ==========================================
# THREADS DE SURVEILLANCE & RESSOURCES
# ==========================================
from src.monitoring.server_status import ServerStatusThread
from src.monitoring.nvidia_status import NvidiaStatusThread
from src.monitoring.runtime_info import RuntimeInfoThread



from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog


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
from src.audio.recorder import AudioRecorderThread


from src.ui.widgets.audio_bars import LiveAudioIndicator, ScrollingAudioBars
from src.ui.widgets.recording_indicator import RecordingIndicator


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
from src.llm.client import LlamaThread

# ==========================================
# ANALYSE LOCALE DE DOCUMENTS — PDF / IMAGES
# ==========================================
from src.documents.pdf_utils import (
    normalize_page_selection as _normalize_page_selection,
    extract_pdf_context as _extract_pdf_context,
    open_pdf_at_page as _open_pdf_at_page,
)
from src.documents.payload_builder import (
    document_image_data_url as _document_image_data_url,
    prepare_document_payload as _prepare_document_payload,
)
from src.documents.thread import DocumentAnalysisThread


from src.ui.widgets.chat_bubble import SourceZoomTextBrowser, ChatBubble
from src.ui.widgets.animated_buttons import AnimatedComposerButton
from src.ui.widgets.attachment_widget import AttachmentPreviewWidget
from src.ui.widgets.message_editor import MessageTextEdit
from src.ui.widgets.thinking_dots import ThinkingDots

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
