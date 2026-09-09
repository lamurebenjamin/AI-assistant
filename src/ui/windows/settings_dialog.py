"""Fenêtre des paramètres de l'assistant (actions, llama-server, voix, TTS, etc.)."""

import copy
import ctypes
import json
import os
import sys
import sounddevice as sd
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPalette
from PyQt5.QtWidgets import (
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
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.schema import APP_DIR, DEFAULT_CONFIG, LOGGER
from src.config.manager import save_config
from src.ui.design_tokens import (
    COLOR_BG_PAGE,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_SUBTLE,
    COLOR_PRIMARY,
    COLOR_TEXT_PRIMARY,
    FONT_TEXT,
    RADIUS_LG,
    RADIUS_MD,
    SIZE_LG,
    SIZE_MD,
)
from src.ui.icons import ICONS, ICONS_DARK, get_logo_pixmap
from src.ui.stylesheet import build_settings_qss
from src.ui.theme import apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.audio.recorder import AudioRecorderThread
from src.monitoring.server_status import ServerStatusThread
from src.monitoring.nvidia_status import NvidiaStatusThread
from src.llm.server_manager import get_server_manager

LLAMA_SERVER_MANAGER = get_server_manager()
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

        self.setStyleSheet(build_settings_qss())

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
        self.header_icon_label.setPixmap(get_logo_pixmap(16, APP_DIR))
        header_layout.addWidget(self.header_icon_label, 0, Qt.AlignVCenter)

        title_label = QLabel("Paramètres", header)
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setTextFormat(Qt.PlainText)
        header_layout.addWidget(title_label, 1)

        close_btn = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", header)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn, 0, Qt.AlignVCenter)
        panel_layout.addWidget(header)

        separator = QFrame(self.panel)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(0,0,0,35); border: none;")
        panel_layout.addWidget(separator)

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
        server_box.setStyleSheet(f"QFrame {{ background: {COLOR_BG_SURFACE}; border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_LG}; }}")
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
        voice_box.setStyleSheet(f"QFrame {{ background: {COLOR_BG_SURFACE}; border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_LG}; }}")
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
        btn_up = QPushButton(); btn_up.setObjectName("ToolButton"); btn_up.setIcon(ICONS_DARK["up"]); btn_up.setToolTip("Monter"); btn_up.clicked.connect(lambda: self.move_action(-1))
        btn_down = QPushButton(); btn_down.setObjectName("ToolButton"); btn_down.setIcon(ICONS_DARK["down"]); btn_down.setToolTip("Descendre"); btn_down.clicked.connect(lambda: self.move_action(1))

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


