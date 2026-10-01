"""Construction de la vue des parametres, par domaine fonctionnel."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import src.ui.design_tokens as t
from src.ui.fluent_compat import CheckBox as QCheckBox
from src.ui.fluent_compat import ComboBox as QComboBox
from src.ui.fluent_compat import LineEdit as QLineEdit
from src.ui.fluent_compat import ListWidget as QListWidget
from src.ui.fluent_compat import PushButton as QPushButton
from src.ui.fluent_compat import TextEdit as QTextEdit
from src.ui.icons import ICONS, ICONS_DARK
from src.ui.stylesheet import build_settings_qss, qss_settings_emphasis
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.status_label import StatusLabel
from src.ui.widgets.window_chrome import WindowChrome
from src.ui.windows.settings_tabs import SettingsTabsBuilder


def build_shell(self):
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
    return panel_layout, content_layout, llm_layout, voice_layout, shortcuts_layout


def build_llm_section(self, llm_layout):
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
        "PROCESSUS DÉMARRÉ" if self._server_manager.is_running() else "PROCESSUS ARRÊTÉ",
        tone="success" if self._server_manager.is_running() else "muted",
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


def build_voice_section(self, voice_layout):
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


def build_shortcuts_section(self, shortcuts_layout):
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


def build_footer(self, panel_layout, content_layout):
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
