"""Fenêtre flottante principale de l'assistant IA avec fond acrylique et gestion du dialogue."""

import copy
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import keyboard
import pyperclip
import sounddevice as sd
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QIcon,
    QPainterPath,
    QPalette,
    QRegion,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.skill_manager import SkillManager
from src.audio.recorder import AudioRecorderThread
from src.config.manager import load_config, save_config
from src.config.schema import APP_DIR, DEFAULT_CONFIG, LOGGER
from src.documents.pdf_utils import open_pdf_at_page as _open_pdf_at_page
from src.documents.thread import DocumentAnalysisThread
from src.llm.client import LlamaThread
from src.llm.response_parser import parse_audio_response, split_thinking_and_answer
from src.llm.server_manager import get_server_manager
from src.monitoring.runtime_info import RuntimeInfoThread
from src.monitoring.server_status import ServerStatusThread
from src.rendering.markdown import format_inline_markdown, markdown_to_html, markdown_to_spoken_text
from src.tts.thread import KokoroTtsThread, KokoroWarmupThread
from src.ui.design_tokens import (
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_SUBTLE,
    COLOR_PRESS_DARK,
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_DISPLAY,
    FONT_TEXT,
    RADIUS_SM,
    RADIUS_MD,
    RADIUS_XL,
    SIZE_LG,
    SIZE_SM,
)
from src.ui.icons import ICONS_DARK, get_logo_pixmap
from src.ui.stylesheet import build_acrylic_window_qss
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.ui.widgets.recording_indicator import RecordingIndicator
from src.ui.windows.document_dialog import DocumentDialog
from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog
from src.ui.windows.settings_dialog import SettingsDialog

LLAMA_SERVER_MANAGER = get_server_manager()
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
        self.panel.setStyleSheet(
            build_acrylic_window_qss()
            + f"""
            QScrollBar:horizontal {{ height: 0; }}
            """
        )

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
        self.header_icon_label.setPixmap(get_logo_pixmap(16, APP_DIR))
        header_layout.addWidget(self.header_icon_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel("Transcript", header)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setTextFormat(Qt.PlainText)
        header_layout.addWidget(self.title_label, 1)

        self.speak_button = AnimatedHeaderButton(ICONS_DARK["speak"], "Lire la réponse à haute voix", header)
        self.speak_button.setIconSize(QSize(18, 18))
        self.speak_button.clicked.connect(self.toggle_speech)
        header_layout.addWidget(self.speak_button, 0, Qt.AlignVCenter)

        self.copy_button = AnimatedHeaderButton(ICONS_DARK["copy"], "Copier la réponse", header)
        self.copy_button.setIconSize(QSize(17, 17))
        self.copy_button.clicked.connect(self.copy_response)
        header_layout.addWidget(self.copy_button, 0, Qt.AlignVCenter)

        self.close_button = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", header)
        self.close_button.setIconSize(QSize(18, 18))
        self.close_button.clicked.connect(self.close_response_window)
        header_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)
        panel_layout.addWidget(header)
        self.separator_container = QFrame(self.panel)
        self.separator_container.setFixedHeight(1)
        self.separator_container.setStyleSheet("background: rgba(0,0,0,35); border: none;")
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
        self.label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                color: {COLOR_TEXT_PRIMARY};
                padding: 10px 14px 10px 14px;
                font-family: {FONT_TEXT};
                font-size: {SIZE_LG};
                line-height: 1.5;
            }}
        """)

        pal = self.label.palette()
        pal.setColor(QPalette.Highlight, QColor(COLOR_PRIMARY_LIGHT))
        pal.setColor(QPalette.HighlightedText, QColor(COLOR_TEXT_PRIMARY))
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

            # Plusieurs tentatives avec délais réduits pour éviter de bloquer l'interface
            # lorsque rien n'est sélectionné.
            for shortcut, timeout in (('ctrl+c', 0.25), ('ctrl+c', 0.35), ('ctrl+insert', 0.35)):
                pyperclip.copy(marker)
                time.sleep(0.04)
                keyboard.send(shortcut)
                copied = read_new_clipboard(timeout)
                if copied:
                    return copied
                time.sleep(0.06)
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
        menu.setStyleSheet(f"""
            QMenu#AssistantMenu {{
                background-color: {COLOR_BG_SURFACE};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-family: {FONT_TEXT};
                font-size: {SIZE_LG};
            }}
            QMenu#AssistantMenu::item {{
                background-color: transparent;
                color: {COLOR_TEXT_PRIMARY};
                min-height: 22px;
                padding: 7px 22px 7px 12px;
                margin: 2px;
                border: none;
                border-radius: {RADIUS_SM};
            }}
            QMenu#AssistantMenu::item:selected {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_TEXT_INVERSE};
            }}
            QMenu#AssistantMenu::separator {{
                height: 1px;
                background-color: {COLOR_BORDER_SUBTLE};
                margin: 6px 10px;
            }}
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
                # Limiter l'historique aux 10 derniers échanges (20 messages) pour éviter la saturation du contexte.
                if len(self.document_history) > 20:
                    self.document_history = self.document_history[-20:]
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
            logo_path = os.path.join(APP_DIR, "logo.png")

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
