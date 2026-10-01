"""Fenetre d'analyse et de dialogue documentaire (PDF, images, texte)."""

import os

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
from qfluentwidgets import RoundMenu

import src.ui.design_tokens as t
from core.skill_manager import SkillManager
from src.ui.icons import create_svg_icon
from src.ui.stylesheet import qss_document_dialog
from src.ui.windows import document_attachment_renderer as _document_attachment_renderer
from src.ui.windows import document_dialog_view as _document_dialog_view
from src.ui.windows import document_skill_controller as _document_skill_controller
from src.ui.windows import document_source_preview as _document_source_preview
from src.ui.windows import document_window_behavior as _document_window_behavior
from src.ui.windows.conversation_controller import ConversationController
from src.ui.windows.document_composer_controller import DocumentComposerController
from src.ui.windows.document_conversation_renderer import DocumentConversationRenderer
from src.ui.windows.document_response_controller import DocumentResponseController


class DocumentDialog(QDialog):
    """Fenêtre Ctrl+9 harmonisée avec les fenêtres de résultats et pensée comme un chat."""
    ask_requested = Signal(list, str, object, object)

    WINDOW_WIDTH = 480
    MIN_HEIGHT = 80
    MAX_HEIGHT = 620
    MAX_RESPONSE_HEIGHT = 440
    FONT_SIZE_OFFSET = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.host = parent
        self.apply_config(initial=True)
        if self.host is not None and hasattr(self.host, "skill_manager"):
            self.skill_manager = self.host.skill_manager
        else:
            self.skill_manager = SkillManager()
            self.skill_manager.discover()
        self._pending_forced_tool = None
        self._pending_skill_tag = None
        self._setting_skill_text = False
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
        self._prompt_history_index = None
        self._prompt_history_draft = ""
        # Références conservées pendant le streaming Ctrl+9. La bulle courante
        # est mise à jour en place au lieu de reconstruire toute la conversation.
        self.current_assistant_bubble = None
        self.current_thinking_widget = None
        self.streaming_response_active = False
        self._allow_shrink_height = False
        self.conversation_controller = ConversationController(self)
        self.response_controller = DocumentResponseController(self)
        self.composer_controller = DocumentComposerController(self)
        self.conversation_renderer = DocumentConversationRenderer(self)
        # Le rendu des fragments SSE est regroupé pour éviter de détruire et
        # reconstruire toute la conversation à chaque token.
        self.pending_stream_render = False
        self.stream_render_timer = QTimer(self)
        self.stream_render_timer.setSingleShot(True)
        self.stream_render_timer.setInterval(45)
        self.stream_render_timer.timeout.connect(self._flush_stream_render)
        self._temp_files = set()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cleanup_temp_files)
        self._build_ui()

    def apply_config(self, ctrl9_config=None, initial=False):
        """Applique la configuration CTRL+9 (largeur, hauteur max, taille police)."""
        if ctrl9_config is None:
            if self.host is not None and hasattr(self.host, "config") and isinstance(self.host.config, dict):
                ctrl9_config = self.host.config.get("ctrl9", {})
            else:
                from src.config.manager import load_config
                ctrl9_config = load_config().get("ctrl9", {})

        self.WINDOW_WIDTH = ctrl9_config.get("width", 480)
        self.MAX_HEIGHT = ctrl9_config.get("max_height", 620)
        font_size = ctrl9_config.get("font_size", 14)
        self.FONT_SIZE_OFFSET = font_size - 13
        self.MAX_RESPONSE_HEIGHT = max(180, self.MAX_HEIGHT - 180)

        self.setFixedWidth(self.WINDOW_WIDTH)
        if hasattr(self, "_attachment_preview"):
            self._attachment_preview.font_size_offset = self.FONT_SIZE_OFFSET
        if hasattr(self, "response"):
            self.response.setMaximumHeight(self.MAX_RESPONSE_HEIGHT)
        if not initial:
            self._apply_font_styles()
            if hasattr(self, "turns") and self.turns:
                self._render_conversation()
            else:
                self._update_height()

    def _apply_font_styles(self):
        self.setStyleSheet(qss_document_dialog(self.FONT_SIZE_OFFSET))
        if hasattr(self, "status"):
            self.status.setObjectName("DocStatus")
        if hasattr(self, "composer") and hasattr(self.composer, "refresh_theme"):
            self.composer.font_size_offset = self.FONT_SIZE_OFFSET
            self.composer.refresh_theme()

    def refresh_theme(self) -> None:
        self._apply_font_styles()
        if hasattr(self, "separator_container"):
            self.separator_container.refresh_theme()
        if hasattr(self, "header"):
            self.header.refresh_logo()
        if hasattr(self, "drop_zone"):
            self.drop_zone.setIcon(
                create_svg_icon(
                    '<path d="M12 5v14M5 12h14"/>',
                    t.COLOR_TEXT_PRIMARY,
                    t.ICON_STROKE_WIDTH,
                )
            )
        if hasattr(self, "mic"):
            self.mic_icon = create_svg_icon(
                '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>'
                '<path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8"/>',
                t.COLOR_TEXT_PRIMARY,
                1.7,
            )
            self.recording_icon = create_svg_icon(
                f'<circle cx="12" cy="12" r="6" fill="{t.COLOR_DANGER}" stroke="none"/>',
                t.COLOR_DANGER,
                1.0,
            )
            if not self.is_recording:
                self.mic.setIcon(self.mic_icon)
            else:
                self.mic.setIcon(self.recording_icon)
        if hasattr(self, "turns") and self.turns:
            self._render_conversation()

    def _build_ui(self):
        return _document_dialog_view._build_ui(self)

    def _open_source_link(self, url):
        return self.conversation_controller.open_source_link(url)

    def _show_source_image_large(self, image_path, source_title="Source surlignée"):
        return _document_source_preview._show_source_image_large(self, image_path, source_title)

    def _answer_without_sources(self, answer):
        return _document_attachment_renderer._answer_without_sources(self, answer)

    def _attachment_preview_html(self, documents):
        return _document_attachment_renderer._attachment_preview_html(self, documents)

    def _take_current_attachments(self):
        """Fige les pièces jointes pour le tour puis vide immédiatement le compositeur."""
        documents = self._specs()
        attachments_html = self._attachment_preview_html(documents)
        self.paths.clear()
        self.page_selections.clear()
        self._show_document(-1)
        return documents, attachments_html

    def _clear_conversation_widgets(self):
        return self.conversation_renderer._clear_conversation_widgets()

    def _clear_turn_navigation(self):
        return self.conversation_renderer._clear_turn_navigation()

    def _render_conversation(self):
        return self.conversation_controller.render()

    def _render_conversation_impl(self):
        return self.conversation_renderer.render()

    def _update_turn_navigation_visibility(self):
        return self.conversation_renderer._update_turn_navigation_visibility()

    def _refresh_conversation_widths(self):
        return self.conversation_renderer._refresh_conversation_widths()

    def _scroll_to_bottom(self):
        return self.conversation_renderer._scroll_to_bottom()

    def _sync_conversation_widget_height(self):
        return self.conversation_renderer._sync_conversation_widget_height()

    def _update_response_scroll_policy(self):
        return self.conversation_renderer._update_response_scroll_policy()

    def _refresh_stream_view(self):
        return self.conversation_renderer._refresh_stream_view()

    def _update_height(self):
        return self.conversation_renderer._update_height()

    def _add_sources_html(self, answer, documents):
        return self.conversation_renderer._add_sources_html(answer, documents)

    def show_source_captures(self, answer, documents):
        return self.conversation_controller.show_source_captures(answer, documents)

    def _header_press(self,event):
        return _document_window_behavior._header_press(self, event)
    def _header_move(self,event):
        return _document_window_behavior._header_move(self, event)
    def _header_release(self,event):
        return _document_window_behavior._header_release(self, event)

    def toggle_collapse(self):
        return _document_window_behavior.toggle_collapse(self)

    def focus_message_input(self):
        """Place immédiatement le curseur dans « Message assistant IA »."""
        if not self.isVisible():
            return
        if self.is_collapsed:
            self.toggle_collapse()
        self.raise_()
        self.activateWindow()
        self.question.setFocus(Qt.ActiveWindowFocusReason)
        cursor = self.question.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.question.setTextCursor(cursor)
        self.question.ensurePolished()

    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self._apply_effects)
        QTimer.singleShot(0,self._update_height)
        # Windows peut appliquer l'activation après show(). Réessayer après les
        # étapes d'activation garantit que la première frappe arrive au champ.
        for delay in (0, 80, 180):
            QTimer.singleShot(delay, self.focus_message_input)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_rounded_masks()

    def _update_rounded_masks(self):
        return _document_window_behavior._update_rounded_masks(self)

    def _apply_effects(self):
        # Applique le flou DWM après la création du HWND. Un seul arrondi est
        # dessiné par Qt sur DocPanel : l'arrondi DWM natif est volontairement
        # désactivé pour éviter un second rayon différent.
        return _document_window_behavior._apply_effects(self)

    def _update_question_height(self):
        return self.composer_controller._update_question_height()

    def _update_send_visibility(self):
        return self.composer_controller._update_send_visibility()

    def _stop_llm_generation(self):
        return self.composer_controller._stop_llm_generation()

    def _ask_text(self):
        return self.composer_controller._ask_text()

    def _prompt_history(self):
        return self.composer_controller._prompt_history()

    def _reset_prompt_history_navigation(self):
        return self.composer_controller._reset_prompt_history_navigation()

    def _navigate_prompt_history(self, direction: int):
        return self.composer_controller._navigate_prompt_history(direction)

    def _set_inline_recording_visual(self, active):
        return self.composer_controller._set_inline_recording_visual(active)

    def _toggle_microphone(self):
        return self.composer_controller._toggle_microphone()

    def _audio_ready(self, data, duration, rms):
        return self.composer_controller._audio_ready(data, duration, rms)

    def _audio_error(self, message):
        return self.composer_controller._audio_error(message)

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
    def _create_add_menu(self) -> RoundMenu:
        return _document_skill_controller._create_add_menu(self)

    def _show_add_menu(self):
        return _document_skill_controller._show_add_menu(self)

    def _on_skill_tool_selected(self, skill_name: str, tool_name: str):
        return _document_skill_controller._on_skill_tool_selected(self, skill_name, tool_name)

    def _skill_tool_details(self, skill_name, tool_name):
        return _document_skill_controller._skill_tool_details(self, skill_name, tool_name)

    def _set_skill_tag(self, tag):
        return _document_skill_controller._set_skill_tag(self, tag)

    def _clear_skill_tag_when_erased(self):
        return _document_skill_controller._clear_skill_tag_when_erased(self)

    def _clear_skill_tag(self):
        return _document_skill_controller._clear_skill_tag(self)

    def _select_skill_tool(self, skill_name, tool_name, existing_text=""):
        return _document_skill_controller._select_skill_tool(self, skill_name, tool_name, existing_text)

    # ------------------------------------------------------------------
    # Slash-command popup handlers
    # ------------------------------------------------------------------
    def _build_slash_actions(self):
        return _document_skill_controller._build_slash_actions(self)

    def _position_slash_popup(self):
        return _document_skill_controller._position_slash_popup(self)

    def _on_slash_triggered(self, query: str, slash_pos: int):
        return _document_skill_controller._on_slash_triggered(self, query, slash_pos)

    def _on_slash_dismissed(self):
        return _document_skill_controller._on_slash_dismissed(self)

    def _on_slash_action_selected(self, action: dict):
        return _document_skill_controller._on_slash_action_selected(self, action)

    def _choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Ajouter des documents","","Documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        self._add_paths(paths)

    @staticmethod
    def _create_pdf_fallback_pixmap(width: int, height: int) -> QPixmap:
        return _document_attachment_renderer._create_pdf_fallback_pixmap(width, height)

    def _page_count(self,path):
        return self._attachment_preview.page_count(path)

    def _add_paths(self, paths):
        self._attachment_preview.add_paths(paths, self._supported)

    def _clear_image_strip(self):
        self._attachment_preview.clear_image_strip()

    def _remove_path(self, path):
        self._attachment_preview.remove_path(path)

    def _rebuild_image_strip(self):
        self._attachment_preview.rebuild_image_strip()

    def _show_document(self, index=-1):
        if not self.paths:
            self._attachment_preview.show_document(index)
            self.status.hide()
            return
        self._attachment_preview.show_document(index)
        self.status.setText("Pi?ces jointes pr?tes")
        self._update_height()

    def _save_page_range(self):
        return

    def _remove_current(self):
        self._attachment_preview.remove_current()

    def _specs(self):
        return [{"path":p,"pages":list(range(self.page_selections[p][0],self.page_selections[p][1]+1))} for p in self.paths]

    def begin_response(self, question, attachments_html="", skill_tag=None, documents=None):
        return self.response_controller.begin_response(
            question, attachments_html, skill_tag, documents
        )

    def append_thinking(self, text):
        return self.response_controller.append_thinking(text)

    def append_response(self, text):
        return self.response_controller.append_response(text)

    def _flush_stream_render(self):
        return self.response_controller._flush_stream_render()

    def _on_tool_widget_toggled(self):
        return self.response_controller._on_tool_widget_toggled()

    def _finish_toggle_layout(self, scroll_bar, previous_value):
        return self.response_controller._finish_toggle_layout(
            scroll_bar, previous_value
        )

    def record_tool_event(self, phase: str, name: str, detail: str):
        return self.response_controller.record_tool_event(phase, name, detail)

    def finish_response(self):
        return self.response_controller.finish_response()

    def show_error(self, message):
        return self.response_controller.show_error(message)

    def cleanup_temp_files(self):
        """Supprime les fichiers temporaires créés pour les aperçus et les captures de sources."""
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self._temp_files.clear()

    def closeEvent(self, event):
        thread = self.host.document_thread if self.host is not None else None
        if thread is not None and thread.isRunning():
            thread.stop()
        self._stop_llm_generation()
        if self.audio_thread is not None and self.audio_thread.isRunning():
            self.audio_thread.stop_recording()
        self.cleanup_temp_files()
        super().closeEvent(event)
