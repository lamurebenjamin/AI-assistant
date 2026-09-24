"""Fenêtre flottante principale de l'assistant IA avec fond acrylique et gestion du dialogue."""

import html
import os
import re
import sys
import time

import keyboard
import pyperclip
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    SmoothScrollArea,
)

import src.ui.design_tokens as t
from core.skill_manager import SkillManager
from src.config.manager import load_config
from src.config.schema import LOGGER
from src.documents.pdf_utils import open_pdf_at_page as _open_pdf_at_page
from src.documents.thread import DocumentAnalysisThread
from src.llm.client import LlamaThread
from src.llm.response_parser import parse_audio_response, split_thinking_and_answer
from src.llm.server_manager import get_server_manager
from src.monitoring.runtime_info import RuntimeInfoThread
from src.rendering.markdown import format_inline_markdown, markdown_to_html
from src.tts.thread import KokoroWarmupThread
from src.ui.controllers.assistant_orchestration import AssistantOrchestrationController
from src.ui.design_tokens import (
    ICON_SIZE_BUTTON,
    ICON_SIZE_CLOSE,
    ICON_SIZE_COPY,
    SIZE_LG,
    SIZE_SM,
)
from src.ui.fluent_compat import install_tooltip
from src.ui.icons import ICONS_DARK
from src.ui.stylesheet import (
    build_acrylic_window_qss,
    qss_assistant_body,
    qss_scrollbar_hidden_horizontal,
)
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedHeaderButton
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.recording_indicator import RecordingIndicator
from src.ui.widgets.tool_call_widget import ThinkingGroupWidget
from src.ui.widgets.window_chrome import WindowChrome
from src.ui.windows.assistant_file_links import created_file_paths, file_link_markdown
from src.ui.windows.assistant_response_renderer import AssistantResponseRenderer
from src.ui.windows.assistant_window_document_controller import (
    AssistantWindowDocumentController,
    AssistantWindowMenuController,
)
from src.ui.windows.assistant_window_geometry import AssistantWindowGeometryController
from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog
from src.ui.windows.settings_dialog import SettingsDialog

LLAMA_SERVER_MANAGER = get_server_manager()

WINDOW_SIZE_LG = f"{int(SIZE_LG.rstrip('px')) + 1}px"
WINDOW_SIZE_SM = f"{int(SIZE_SM.rstrip('px')) + 1}px"


class AssistantWindow(QWidget):
    show_menu_signal = Signal()
    trigger_direct_signal = Signal(int)
    toggle_collapse_signal = Signal()
    voice_press_signal = Signal(int)
    voice_release_signal = Signal(int)
    voice_cancel_signal = Signal()

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
            _ok, message = LLAMA_SERVER_MANAGER.start(self.config)
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
        self.document_dialog_position = None
        self.document_source_pages = []
        self.document_documents = []
        # Documents cumulés de la conversation Ctrl+9. Ils restent disponibles
        # pour toutes les questions de suivi, même sans nouvelle pièce jointe.
        self.document_session_documents = []
        self.document_response_active = False
        self.document_history = []
        self.recording_indicator = RecordingIndicator()
        self.recording_indicator.cancel_requested.connect(self.cancel_voice_operation)
        self.orchestration = AssistantOrchestrationController(self)
        self.response_renderer = AssistantResponseRenderer(self)
        self.menu_controller = AssistantWindowMenuController(self)
        self.document_controller = AssistantWindowDocumentController(self)
        self.geometry_controller = AssistantWindowGeometryController(self)

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
            self.config.get("api_url", ""),
            process_ids,
            self,
            LLAMA_SERVER_MANAGER.auth_token,
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
        return self.orchestration.start_server_online_notification(tray_icon)

    def check_startup_server_status(self):
        return self.orchestration.check_startup_server_status()

    def on_startup_status_finished(self):
        return self.orchestration.on_startup_status_finished()

    def handle_startup_server_status(self, online, detail, model_name):
        return self.orchestration.handle_startup_server_status(online, detail, model_name)

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("AssistantWindow")

        self.resize(390, 35)
        self.setMinimumSize(250, 35)
        self.setMaximumSize(1400, 900)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("AcrylicPanel")
        self.panel.setStyleSheet(
            build_acrylic_window_qss(font_offset=1)
            + qss_assistant_body()
            + qss_scrollbar_hidden_horizontal()
        )

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = WindowChrome("Transcript", self.panel)
        header.mousePressEvent = self.mousePressEvent
        header.mouseMoveEvent = self.mouseMoveEvent
        header.mouseReleaseEvent = self.mouseReleaseEvent
        self.chrome = header
        self.header_icon_label = header.icon_label
        self.title_label = header.title_label

        self.speak_button = AnimatedHeaderButton(ICONS_DARK["speak"], "Lire la réponse à haute voix", header, is_audio=True)
        self.speak_button.setIconSize(QSize(ICON_SIZE_BUTTON, ICON_SIZE_BUTTON))
        self.speak_button.clicked.connect(self.toggle_speech)
        header.add_action(self.speak_button)

        self.copy_button = AnimatedHeaderButton(ICONS_DARK["copy"], "Copier la réponse", header)
        self.copy_button.setIconSize(QSize(ICON_SIZE_COPY, ICON_SIZE_COPY))
        self.copy_button.clicked.connect(self.copy_response)
        header.add_action(self.copy_button)

        self.close_button = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", header)
        self.close_button.setIconSize(QSize(ICON_SIZE_CLOSE, ICON_SIZE_CLOSE))
        self.close_button.clicked.connect(self.close_response_window)
        header.add_action(self.close_button)
        panel_layout.addWidget(header)
        self.separator_container = HairlineSeparator(self.panel)
        self.separator_wrapper = self.separator_container
        self.separator = self.separator_container.line
        panel_layout.addWidget(self.separator_container)

        self.thinking_widget = ThinkingGroupWidget(self.panel)
        self.thinking_widget.hide()
        panel_layout.addWidget(self.thinking_widget)

        self.scroll_area = SmoothScrollArea(self.panel)
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
        self.label.setObjectName("TranscriptBody")
        self.label.setStyleSheet("")

        pal = self.label.palette()
        pal.setColor(QPalette.Highlight, QColor(t.COLOR_PRIMARY_LIGHT))
        pal.setColor(QPalette.HighlightedText, QColor(t.COLOR_TEXT_PRIMARY))
        self.label.setPalette(pal)
        self.scroll_area.setWidget(self.label)
        panel_layout.addWidget(self.scroll_area, 1)

        # Visible uniquement pendant l'exécution d'un outil.
        self.tool_status_label = QLabel("", self.panel)
        self.tool_status_label.setObjectName("ToolStatus")
        self.tool_status_label.setTextFormat(Qt.PlainText)
        self.tool_status_label.setStyleSheet("")
        self.tool_status_label.hide()
        panel_layout.addWidget(self.tool_status_label)

        self.layout.addWidget(self.panel)

    def refresh_theme(self) -> None:
        if not hasattr(self, "panel"):
            return
        self.panel.setStyleSheet(
            build_acrylic_window_qss(font_offset=1)
            + qss_assistant_body()
            + qss_scrollbar_hidden_horizontal()
        )
        pal = self.label.palette()
        pal.setColor(QPalette.Highlight, QColor(t.COLOR_PRIMARY_LIGHT))
        pal.setColor(QPalette.HighlightedText, QColor(t.COLOR_TEXT_PRIMARY))
        self.label.setPalette(pal)
        if hasattr(self, "separator_wrapper"):
            self.separator_wrapper.refresh_theme()
        if hasattr(self, "chrome"):
            self.chrome.refresh_logo()
        self.close_button.setIcon(ICONS_DARK["close"])
        speaking = self.tts_thread is not None and self.tts_thread.isRunning()
        self.speak_button.setIcon(ICONS_DARK["stop"] if speaking else ICONS_DARK["speak"])
        self.copy_button.setIcon(ICONS_DARK["copy"])
        if hasattr(self, "recording_indicator"):
            self.recording_indicator.refresh_theme()

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
        return self.geometry_controller.update_rounded_mask()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.geometry_controller.resize_event(event)

    def stop_height_animation(self):
        """Arrête proprement l'animation avant tout redimensionnement manuel."""
        self.geometry_controller.stop_height_animation()

    def calculate_expanded_height(self):
        """Calcule la hauteur utile à partir du contenu réellement affiché."""
        return self.geometry_controller.calculate_expanded_height()

    def animate_height(self, target, expanding):
        self.geometry_controller.animate_height(target, expanding)

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
        except Exception:  # noqa: BLE001
            clipboard_backup = ""

        marker = f"__ASSISTANT_COPY_{time.monotonic_ns()}__"

        def read_new_clipboard(timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                time.sleep(0.04)
                try:
                    value = pyperclip.paste()
                except Exception:  # noqa: BLE001
                    LOGGER.debug("Lecture du presse-papiers indisponible", exc_info=True)
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
                except Exception:  # noqa: BLE001,S110
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
            except Exception:  # noqa: BLE001,S110
                pass

    def _show_menu_impl(self):
        self.menu_controller.show_menu()

    def toggle_open_window_collapse(self):
        """Ctrl+0 masque ou réaffiche la fenêtre Ctrl+9 actuellement ouverte."""
        self.document_controller.toggle_window()

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
        self.document_controller.show_dialog()

    def _remember_document_dialog_position(self, _result=0):
        self.document_controller.remember_position(_result)

    def _restore_document_dialog_position(self, dialog):
        self.document_controller._restore_position(dialog)

    def start_document_analysis(self, paths, question, audio_data=None, forced_tool=None):
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
            forced_tool=forced_tool,
            auth_token=LLAMA_SERVER_MANAGER.auth_token,
        )
        self.document_thread.new_text.connect(self.update_document_text)
        self.document_thread.thinking_text.connect(self.update_document_thinking)
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
        if self.document_dialog is not None:
            self.document_dialog.record_tool_event(phase, name, detail)
        if phase == "résultat":
            for path in self._created_file_paths(detail):
                self.update_document_text(self._file_link_markdown(path))

    def update_document_text(self, text):
        self.response_text += text
        if self.document_dialog is not None: self.document_dialog.append_response(text)

    def update_document_thinking(self, text):
        if self.document_dialog is not None:
            self.document_dialog.append_thinking(text)

    def open_document_source(self, filename, page):
        """Ouvre le document demandé par un lien de source, à la bonne page."""
        decoded_name = filename.strip().lstrip("-•* ").strip()
        requested_name = os.path.basename(decoded_name).casefold()
        for document in self.document_documents:
            path = document.get("path") if isinstance(document, dict) else document
            if os.path.basename(path).casefold() == requested_name:
                try:
                    _open_pdf_at_page(path, int(page))
                except Exception:  # noqa: BLE001
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
                except Exception: LOGGER.exception("Impossible d'ouvrir le PDF cité")  # noqa: BLE001
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
        return self.orchestration.set_hotkeys_enabled(enabled, persist)

    def toggle_hotkeys(self, enabled=None):
        """Inverse l'état des raccourcis ou applique l'état fourni par Qt."""
        if enabled is None:
            enabled = not bool(self.config.get("hotkeys_enabled", True))
        self.set_hotkeys_enabled(enabled)

    def set_automatic_reading_enabled(self, enabled, persist=True):
        return self.orchestration.set_automatic_reading_enabled(enabled, persist)

    def toggle_automatic_reading(self):
        """Inverse la lecture automatique depuis l'icône système."""
        current = self._automatic_tts_enabled()
        self.set_automatic_reading_enabled(not current)

    def quit_application(self):
        self.shutdown_background_threads()
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

    def shutdown_background_threads(self):
        """Arrête et attend tous les threads avant la destruction de la fenêtre."""
        if getattr(self, "_shutdown_started", False):
            return
        self._shutdown_started = True

        for timer_name in (
            "loading_timer",
            "stream_render_timer",
            "startup_status_timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()

        threads = (
            ("llama", self.thread, "stop"),
            ("document", self.document_thread, "stop"),
            ("audio", self.audio_thread, "stop_recording"),
            ("tts", self.tts_thread, "stop"),
            ("runtime-info", self.runtime_info_thread, None),
            ("startup-status", getattr(self, "startup_status_thread", None), None),
            ("kokoro-warmup", self.kokoro_warmup_thread, None),
        )

        self.stop_speech()
        self.recording_indicator.hide()

        for name, thread, stop_method in threads:
            if thread is None or not thread.isRunning():
                continue
            if stop_method is not None:
                stop = getattr(thread, stop_method, None)
                if stop is not None:
                    stop()
            else:
                thread.requestInterruption()
            if not thread.wait(10000):
                LOGGER.warning(
                    "Le thread %s n'a pas terminé avant la fermeture de l'application",
                    name,
                )

        self.thread = None
        self.document_thread = None
        self.audio_thread = None
        self.tts_thread = None
        self.runtime_info_thread = None
        self.startup_status_thread = None

    def open_settings(self):
        self.cancel_voice_operation()
        manager = getattr(QApplication.instance(), "voice_hotkey_manager", None)
        if manager is not None: manager.set_enabled(False)
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = load_config()
            self.set_automatic_reading_enabled(
                self._automatic_tts_enabled(), persist=False
            )
            if self.document_dialog is not None:
                self.document_dialog.apply_config(self.config.get("ctrl9", {}))
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
        install_tooltip(self.title_label, title)

    parse_audio_response = staticmethod(parse_audio_response)
    format_inline_markdown = staticmethod(format_inline_markdown)
    markdown_to_html = staticmethod(markdown_to_html)
    split_thinking_and_answer = staticmethod(split_thinking_and_answer)


    def render_response(self, status_text=""):
        return self.response_renderer.render_response(status_text)

    def update_loading_animation(self):
        return self.response_renderer.update_loading_animation()

    def update_text(self, text):
        return self.response_renderer.update_text(text)

    def flush_stream_text(self):
        return self.response_renderer.flush_stream_text()

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
        return self.orchestration.toggle_speech()

    def _automatic_tts_enabled(self):
        return self.orchestration.automatic_tts_enabled()

    def queue_streaming_speech(self, text, flush=False):
        return self.orchestration.queue_streaming_speech(text, flush)

    def _start_next_tts_segment(self):
        return self.orchestration._start_next_tts_segment()

    def _on_tts_segment_finished(self):
        return self.orchestration._on_tts_segment_finished()

    def stop_speech(self):
        return self.orchestration.stop_speech()

    def on_speech_finished(self):
        return self.orchestration.on_speech_finished()

    def on_speech_failed(self, detail):
        return self.orchestration.on_speech_failed(detail)

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
        except Exception:  # noqa: BLE001
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
        return self.orchestration.selected_voice_device()

    def start_voice_recording(self, index):
        return self.orchestration.start_voice_recording(index)

    def stop_voice_recording(self, index):
        return self.orchestration.stop_voice_recording(index)


    def cancel_voice_operation(self):
        return self.orchestration.cancel_voice_operation()

    def handle_voice_audio(self, audio_data, duration, rms):
        return self.orchestration.handle_voice_audio(audio_data, duration, rms)

    def handle_voice_error(self, message):
        return self.orchestration.handle_voice_error(message)

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
        self.thinking_widget.clear()
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
            max_tokens=self.config.get("llm_max_tokens", 8192),
            auth_token=LLAMA_SERVER_MANAGER.auth_token,
        )
        self.thread.new_text.connect(self.update_text)
        self.thread.thinking_text.connect(self.update_thinking)
        self.thread.tool_event.connect(self.update_tool_event)
        self.thread.new_text.connect(lambda _text: self.recording_indicator.hide())
        self.thread.request_error.connect(self.handle_voice_request_error)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def update_thinking(self, text):
        """Affiche séparément le raisonnement streaming de Gemma."""
        if not text:
            return
        if self.loading_timer.isActive():
            self.loading_timer.stop()
        self.thinking_widget.append_text(text)
        self.thinking_widget.updateGeometry()
        self.panel.layout().invalidate()
        self.panel.layout().activate()
        if self.isVisible() and not self.is_collapsed:
            self.stop_height_animation()
            self.expanded_height = self.calculate_expanded_height()
            self.resize(self.width(), self.expanded_height)

    def handle_voice_request_error(self, message, incompatible):
        self.request_failed = True
        self.voice_sending = False
        self.recording_indicator.hide()
        self.label.setText(f"⚠️ {html.escape(message)}")
        self.show_window()

    def show_window(self, preserve_position=False):
        self.geometry_controller.show_window(preserve_position)
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _created_file_paths(detail):
        return created_file_paths(detail)

    @staticmethod
    def _file_link_markdown(path):
        return file_link_markdown(path)

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
        apply_acrylic_blur(hwnd)
        apply_rounded_corners(hwnd)
        self.update_rounded_mask()
        QTimer.singleShot(0, self.update_rounded_mask)
