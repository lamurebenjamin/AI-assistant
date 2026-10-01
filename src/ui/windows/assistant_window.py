"""Fenêtre flottante principale de l'assistant IA avec fond acrylique et gestion du dialogue."""


from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)

from core.skill_manager import SkillManager
from src.config.manager import load_config
from src.config.schema import LOGGER
from src.llm.response_parser import parse_audio_response, split_thinking_and_answer
from src.llm.server_manager import get_server_manager
from src.rendering.markdown import format_inline_markdown, markdown_to_html
from src.tts.thread import KokoroWarmupThread
from src.ui.controllers.assistant_orchestration import AssistantOrchestrationController
from src.ui.design_tokens import (
    SIZE_LG,
    SIZE_SM,
)
from src.ui.widgets.recording_indicator import RecordingIndicator
from src.ui.windows import assistant_window_clipboard as _assistant_window_clipboard
from src.ui.windows import (
    assistant_window_document_session as _assistant_window_document_session,
)
from src.ui.windows import assistant_window_lifecycle as _assistant_window_lifecycle
from src.ui.windows import (
    assistant_window_request_controller as _assistant_window_request_controller,
)
from src.ui.windows import assistant_window_runtime as _assistant_window_runtime
from src.ui.windows import assistant_window_view as _assistant_window_view
from src.ui.windows.assistant_file_links import created_file_paths, file_link_markdown
from src.ui.windows.assistant_response_renderer import AssistantResponseRenderer
from src.ui.windows.assistant_window_document_controller import (
    AssistantWindowDocumentController,
    AssistantWindowMenuController,
)
from src.ui.windows.assistant_window_geometry import AssistantWindowGeometryController

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
        "Ouvre une fenêtre et actualise les ressources de l'application."
        return _assistant_window_runtime.show_runtime_information(self, server_manager=LLAMA_SERVER_MANAGER)

    def _display_runtime_information(self, information):
        return _assistant_window_runtime._display_runtime_information(self, information)

    def _on_runtime_info_finished(self):
        return _assistant_window_runtime._on_runtime_info_finished(self)

    def start_server_online_notification(self, tray_icon):
        return self.orchestration.start_server_online_notification(tray_icon)

    def check_startup_server_status(self):
        return self.orchestration.check_startup_server_status()

    def on_startup_status_finished(self):
        return self.orchestration.on_startup_status_finished()

    def handle_startup_server_status(self, online, detail, model_name):
        return self.orchestration.handle_startup_server_status(online, detail, model_name)

    def initUI(self):
        return _assistant_window_view.initUI(self)

    def refresh_theme(self) -> None:
        return _assistant_window_view.refresh_theme(self)

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
        'Copie de façon fiable le texte sélectionné, y compris dans les lecteurs PDF.'
        return _assistant_window_clipboard.get_selected_text(self)

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
        "Analyse une nouvelle question en conservant l'historique de la conversation."
        return _assistant_window_document_session.start_document_analysis(self, paths, question, audio_data, forced_tool, server_manager=LLAMA_SERVER_MANAGER)

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
        return _assistant_window_document_session.update_document_tool_event(self, phase, name, detail)

    def update_document_text(self, text):
        return _assistant_window_document_session.update_document_text(self, text)

    def update_document_thinking(self, text):
        return _assistant_window_document_session.update_document_thinking(self, text)

    def open_document_source(self, filename, page):
        'Ouvre le document demandé par un lien de source, à la bonne page.'
        return _assistant_window_document_session.open_document_source(self, filename, page)

    def _open_first_cited_pdf(self, answer):
        'Ouvre le premier PDF réellement cité dans la réponse, à la bonne page.'
        return _assistant_window_document_session._open_first_cited_pdf(self, answer)

    def handle_document_error(self, message, _incompatible):
        return _assistant_window_document_session.handle_document_error(self, message, _incompatible)


    def on_document_finished(self):
        return _assistant_window_document_session.on_document_finished(self)
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
        return _assistant_window_lifecycle.quit_application(self, server_manager=LLAMA_SERVER_MANAGER)

    def shutdown_background_threads(self):
        'Arrête et attend tous les threads avant la destruction de la fenêtre.'
        return _assistant_window_lifecycle.shutdown_background_threads(self)

    def open_settings(self):
        return _assistant_window_lifecycle.open_settings(self)

    def update_window_title(self):
        return _assistant_window_view.update_window_title(self)

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
        return _assistant_window_request_controller.stop_generation(self)

    def close_response_window(self):
        self.stop_generation()
        self.stop_speech()
        self.hide()

    def animate_copy_button(self):
        "Remplace brièvement l'icône Copier par une coche, puis la restaure."
        return _assistant_window_view.animate_copy_button(self)

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
        "Ouvre explicitement les fichiers locaux avec l'application Windows associée."
        return _assistant_window_clipboard.open_response_link(self, href)

    def copy_response(self):
        return _assistant_window_clipboard.copy_response(self)

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
        return _assistant_window_request_controller.trigger_action(self, index, user_text_override, audio_data, audio_format)

    def execute_action(self, action_cfg, preserve_position=False, audio_data=None, audio_format=None):
        return _assistant_window_request_controller.execute_action(self, action_cfg, preserve_position, audio_data, audio_format, server_manager=LLAMA_SERVER_MANAGER)

    def update_thinking(self, text):
        'Affiche séparément le raisonnement streaming de Gemma.'
        return _assistant_window_request_controller.update_thinking(self, text)

    def handle_voice_request_error(self, message, incompatible):
        return _assistant_window_request_controller.handle_voice_request_error(self, message, incompatible)

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
        "Affiche seulement le nom de l'outil, uniquement pendant son exécution."
        return _assistant_window_request_controller.update_tool_event(self, phase, name, detail)

    def on_finished(self):
        return _assistant_window_request_controller.on_finished(self)

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
        return _assistant_window_view.apply_native_window_effects(self)
