"""Fenêtre des paramètres de l'assistant (actions, llama-server, voix, TTS, etc.)."""

import copy
import ctypes
import sys

import sounddevice as sd
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# QFluentWidgets : intégration Windows 11 native
from src.ui.fluent_compat import (
    CheckBox,
    ComboBox,
    LineEdit,
    ListWidget,
    PushButton,
    SpinBox,
    TextEdit,
)

# Alias pour compatibilité avec le code existant qui utilise ces noms
QCheckBox = CheckBox
QComboBox = ComboBox
QLineEdit = LineEdit
QListWidget = ListWidget
QTextEdit = TextEdit
QPushButton = PushButton
QSpinBox = SpinBox

import src.ui.design_tokens as t
from src.audio.recorder import AudioRecorderThread
from src.config.manager import save_config
from src.config.schema import DEFAULT_CONFIG, LOGGER
from src.llm.server_manager import get_server_manager
from src.monitoring.nvidia_status import NvidiaStatusThread
from src.monitoring.server_status import ServerStatusThread
from src.ui.icons import ICONS, ICONS_DARK
from src.ui.stylesheet import (
    build_settings_qss,
    qss_ctrl9_preview,
    qss_settings_emphasis,
)
from src.ui.theme import apply_app_theme, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.status_label import StatusLabel
from src.ui.widgets.window_chrome import WindowChrome
from src.ui.windows.settings_config import (
    copy_server_config,
    normalize_api_url,
    normalize_server_config,
)
from src.ui.windows.settings_tabs import SettingsTabsBuilder

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
        self.temp_server_config = copy_server_config(config.get("llama_server"))
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

        self.header = WindowChrome("Paramètres", self.panel)
        self.header.setMouseTracking(True)
        self.header.installEventFilter(self)
        self.header_icon_label = self.header.icon_label
        self.close_btn = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", self.header)
        self.close_btn.setIconSize(QSize(t.ICON_SIZE_CLOSE, t.ICON_SIZE_CLOSE))
        self.close_btn.clicked.connect(self.reject)
        self.header.add_action(self.close_btn)
        panel_layout.addWidget(self.header)

        self.separator_wrapper = HairlineSeparator(self.panel)
        self.separator = self.separator_wrapper.line
        panel_layout.addWidget(self.separator_wrapper)

        self.content_widget = QWidget(self.panel)
        self.content_widget.setObjectName("SettingsContent")
        self.content_widget.setEnabled(True)
        self.content_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.content_widget.setAttribute(Qt.WA_NoSystemBackground, False)
        self.content_widget.setAutoFillBackground(True)
        self.content_widget.setStyleSheet("")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(22, 18, 22, 18)
        content_layout.setSpacing(12)

        # Organisation des paramètres par domaine fonctionnel.
        tabs = SettingsTabsBuilder(self).build()
        self.settings_tabs = tabs.widget
        self.settings_stack = tabs.stack
        llm_layout = tabs.llm_layout
        voice_layout = tabs.voice_layout
        shortcuts_layout = tabs.shortcuts_layout
        content_layout.addWidget(self.settings_tabs)
        content_layout.addWidget(self.settings_stack, 1)

        # URL, état du serveur et modèle affichés sur trois lignes distinctes.
        api_line_layout = QHBoxLayout()
        api_line_layout.setSpacing(8)
        status_line_layout = QHBoxLayout()
        status_line_layout.setSpacing(8)
        model_line_layout = QHBoxLayout()
        model_line_layout.setSpacing(8)

        api_label = QLabel("URL API llama.cpp")
        api_label.setStyleSheet(qss_settings_emphasis(bold=True))

        self.api_input = QLineEdit(self.temp_api_url)
        self.api_input.setFixedHeight(t.INPUT_HEIGHT)
        self.api_input.setMinimumWidth(250)
        self.api_input.textChanged.connect(self.schedule_server_status_check)

        status_title = StatusLabel("État du serveur :", tone="title", weight=600)
        status_title.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        self.server_status_label = StatusLabel("", tone="warning", weight=600)
        self.server_status_label.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Preferred
        )

        self.server_status_detail = StatusLabel("", tone="muted", weight=400)
        self.server_status_detail.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Preferred
        )

        model_title = StatusLabel("Modèle LLM :", tone="title", weight=600)
        self.server_model_label = StatusLabel("INDISPONIBLE", tone="info", weight=600)
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

        self.server_box = QFrame()
        self.server_box.setObjectName("SettingsCard")
        server_form = QFormLayout(self.server_box)
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
        self.server_process_status = StatusLabel(
            "PROCESSUS DÉMARRÉ" if LLAMA_SERVER_MANAGER.is_running() else "PROCESSUS ARRÊTÉ",
            tone="success" if LLAMA_SERVER_MANAGER.is_running() else "muted",
            weight=700,
        )
        process_row.addWidget(self.server_process_status, 1)
        start_btn = QPushButton("Démarrer"); start_btn.clicked.connect(self.start_local_server)
        stop_btn = QPushButton("Arrêter"); stop_btn.clicked.connect(self.stop_local_server)
        process_row.addWidget(start_btn); process_row.addWidget(stop_btn)
        server_form.addRow("Exécutable", exe_row)
        server_form.addRow("Modèle GGUF", model_row)
        server_form.addRow("Arguments", self.server_args_input)
        server_form.addRow("", self.server_autostart_check)
        server_form.addRow("Processus", process_row)
        llm_layout.addWidget(self.server_box)

        # État du GPU sur une seule ligne, sans libellé superflu.
        gpu_line_layout = QHBoxLayout()
        gpu_line_layout.setSpacing(8)

        self.gpu_pstate_label = StatusLabel("", tone="warning", weight=700)
        self.gpu_detail_label = StatusLabel("", tone="muted", weight=400)
        self.gpu_detail_label.setToolTip("Nom du GPU, utilisation, VRAM et température")
        gpu_line_layout.addWidget(self.gpu_pstate_label)
        gpu_line_layout.addWidget(self.gpu_detail_label, 1)
        llm_layout.addLayout(gpu_line_layout)
        llm_layout.addStretch(1)

        self.voice_box = QFrame()
        self.voice_box.setObjectName("SettingsCard")
        voice_form = QFormLayout(self.voice_box)
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
        voice_layout.addWidget(self.voice_box)
        voice_layout.addStretch(1)
        self.refresh_audio_devices()

        info_label = QLabel("Astuce : Ctrl+1 à Ctrl+9 utilisent le texte sélectionné. Ctrl+Alt+1 à Ctrl+Alt+9 utilisent la voix avec la même action. Ctrl+0 masque/réaffiche Ctrl+9.")
        info_label.setObjectName("SettingsHintItalic")
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
        self.btn_add = QPushButton(" Ajouter"); self.btn_add.setIcon(ICONS_DARK["add"]); self.btn_add.clicked.connect(self.add_action)
        self.btn_del = QPushButton(" Supprimer"); self.btn_del.setIcon(ICONS_DARK["delete"]); self.btn_del.clicked.connect(self.del_action)
        self.btn_up = QPushButton(); self.btn_up.setObjectName("ToolButton"); self.btn_up.setIcon(ICONS_DARK["up"]); self.btn_up.setToolTip("Monter"); self.btn_up.clicked.connect(lambda: self.move_action(-1))
        self.btn_down = QPushButton(); self.btn_down.setObjectName("ToolButton"); self.btn_down.setIcon(ICONS_DARK["down"]); self.btn_down.setToolTip("Descendre"); self.btn_down.clicked.connect(lambda: self.move_action(1))

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        actions_layout.addLayout(btn_layout, 0)
        shortcuts_layout.addLayout(actions_layout, 1)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(t.INPUT_HEIGHT)
        self.sys_prompt_input = QTextEdit()
        self.sys_prompt_input.setMinimumHeight(115)
        self.prefix_input = QLineEdit()
        self.prefix_input.setFixedHeight(t.INPUT_HEIGHT)

        self.name_input.textChanged.connect(self.update_action_field)
        self.sys_prompt_input.textChanged.connect(self.update_action_field)
        self.prefix_input.textChanged.connect(self.update_action_field)

        form_layout.addRow("Nom du raccourcis", self.name_input)
        form_layout.addRow("Prompt Système", self.sys_prompt_input)
        form_layout.addRow("Préfixe", self.prefix_input)
        shortcuts_layout.addLayout(form_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.setIcon(ICONS_DARK["cancel"])
        self.btn_cancel.setIconSize(QSize(t.ICON_SIZE_DIALOG, t.ICON_SIZE_DIALOG))
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Sauvegarder")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.setIcon(ICONS["save"])
        self.btn_save.setIconSize(QSize(t.ICON_SIZE_DIALOG, t.ICON_SIZE_DIALOG))
        self.btn_save.setMinimumHeight(38)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.save)

        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_save)
        content_layout.addLayout(bottom_layout)

        panel_layout.addWidget(self.content_widget)

        self.main_layout.addWidget(self.panel)
        self.panel.setEnabled(True)
        self.content_widget.setEnabled(True)
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
            if event.type() == QEvent.MouseButtonDblClick:
                event.accept()
                return True

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
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
                    event.type() == QEvent.MouseMove and
                    self.drag_position is not None and
                    event.buttons() & Qt.LeftButton):
                self.move(event.globalPos() - self.drag_position)
                event.accept()
                return True

            if event.type() == QEvent.MouseButtonRelease:
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
            self.api_input.text(), self, LLAMA_SERVER_MANAGER.auth_token
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
        return normalize_server_config(
            self.server_autostart_check.isChecked(),
            self.server_exe_input.text(),
            self.server_model_input.text(),
            self.server_args_input.toPlainText().splitlines(),
        )

    def start_local_server(self):
        runtime = dict(self.config); runtime['llama_server'] = self.collect_server_config()
        ok, message = LLAMA_SERVER_MANAGER.start(runtime)
        self.server_process_status.setText("PROCESSUS DÉMARRÉ" if ok else "ÉCHEC DU DÉMARRAGE")
        self.server_process_status.set_tone("success" if ok else "danger", weight=700)
        self.server_process_status.setToolTip(message)
        QTimer.singleShot(800, self.refresh_runtime_status)

    def stop_local_server(self):
        ok, message = LLAMA_SERVER_MANAGER.stop()
        self.server_process_status.setText("PROCESSUS ARRÊTÉ" if ok else "ÉCHEC DE L'ARRÊT")
        self.server_process_status.set_tone("muted" if ok else "danger", weight=700)
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
        except Exception as error:  # noqa: BLE001
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

    def _on_theme_preview_changed(self, _index=None):
        new_theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
        app = QApplication.instance()
        if app:
            apply_app_theme(app, new_theme)
        else:
            self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(build_settings_qss())
        if hasattr(self, "separator_wrapper"):
            self.separator_wrapper.refresh_theme()
        if hasattr(self, "header"):
            self.header.refresh_logo()
        for label in self.findChildren(StatusLabel):
            label.refresh_theme()
        if hasattr(self, "close_btn"):
            self.close_btn.setIcon(ICONS_DARK["close"])
        if hasattr(self, "btn_add"):
            self.btn_add.setIcon(ICONS_DARK["add"])
            self.btn_del.setIcon(ICONS_DARK["delete"])
            self.btn_up.setIcon(ICONS_DARK["up"])
            self.btn_down.setIcon(ICONS_DARK["down"])
        if hasattr(self, "btn_cancel"):
            self.btn_cancel.setIcon(ICONS_DARK["cancel"])
            self.btn_save.setIcon(ICONS["save"])
        if hasattr(self, "ctrl9_font_size_spin"):
            self._refresh_ctrl9_preview(self.ctrl9_font_size_spin.value())

    def _refresh_ctrl9_preview(self, val=None):
        size = int(val if val is not None else self.ctrl9_font_size_spin.value())
        self.ctrl9_preview_label.setStyleSheet(qss_ctrl9_preview(size))

    def save(self):
        selected = self.voice_device_combo.currentData()
        self.config['voice_input'] = copy.deepcopy(self.temp_voice_config)
        self.config['voice_input']['enabled'] = self.voice_enabled_check.isChecked()
        self.config['voice_input']['input_device'] = selected.get("index") if isinstance(selected, dict) else None
        self.config['voice_input']['input_device_name'] = selected.get("name", "") if isinstance(selected, dict) else ""
        self.config['text_to_speech'] = copy.deepcopy(self.temp_tts_config)
        self.config['text_to_speech']['automatic_reading'] = self.automatic_reading_check.isChecked()
        self.config["api_url"] = normalize_api_url(self.api_input.text())
        self.config['llama_server'] = self.collect_server_config()
        self.config['actions'] = self.temp_actions
        if hasattr(self, 'theme_combo'):
            chosen_theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
            self.config['theme'] = chosen_theme
            app = QApplication.instance()
            if app:
                apply_app_theme(app, chosen_theme)
        if hasattr(self, 'ctrl9_width_spin'):
            self.config['ctrl9'] = {
                'width': self.ctrl9_width_spin.value(),
                'max_height': self.ctrl9_max_height_spin.value(),
                'font_size': self.ctrl9_font_size_spin.value(),
            }
        save_config(self.config)
        self.accept()
