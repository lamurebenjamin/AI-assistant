"""Response rendering and streaming view orchestration for AssistantWindow."""

import html
import os
import sys

import src.ui.design_tokens as t
from src.config.schema import APP_DIR


class AssistantResponseRenderer:
    """Owns response HTML rendering while preserving AssistantWindow callbacks."""

    def __init__(self, host):
        self.host = host

    def render_response(self, status_text=""):
        host = self.host
        if status_text:
            content = (
                f'<div style="color:{t.COLOR_STATUS_SUBTLE}; font-style:italic;">'
                f'{html.escape(status_text)}'
                '</div>'
            )
        else:
            _, answer_text = host.split_thinking_and_answer(host.response_text)
            if host.current_request_is_audio:
                transcript, answer_text = host.parse_audio_response(answer_text)
                if transcript:
                    host.title_label.setText(transcript)
                    host.title_label.setToolTip(transcript)
            elif host.document_response_active:
                host.title_label.setText("Documents")
                host.title_label.setToolTip("Analyse documentaire")
            content = host.markdown_to_html(answer_text, 1) if answer_text else ''

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

        host.label.setText(final_html)

    def update_loading_animation(self):
        host = self.host
        host.loading_dot_count = (host.loading_dot_count % 3) + 1
        dots = "." * host.loading_dot_count
        host.render_response(f"{host.loading_action_name}{dots}")


    def update_text(self, text):
        host = self.host
        # Le premier fragment doit stopper immediatement l'indicateur d'attente.
        if host.loading_timer.isActive():
            host.loading_timer.stop()
        if host.thinking_widget.isVisible():
            host.thinking_widget.collapse()
        host.pending_stream_text += text
        host.queue_streaming_speech(text)
        if not host.stream_render_timer.isActive():
            host.stream_render_timer.start()

    def flush_stream_text(self):
        host = self.host
        if not host.pending_stream_text:
            return
        host.response_text += host.pending_stream_text
        host.pending_stream_text = ""
        # Méthode de streaming issue de Assistant_streamok.py : rendu rapide,
        # ajustement immédiat du contenu et de la hauteur à chaque lot de tokens.
        host.render_response()
        host.label.adjustSize()
        if not host.is_collapsed:
            host.stop_height_animation()
            host.expanded_height = host.calculate_expanded_height()
            host.resize(host.width(), host.expanded_height)
        scrollbar = host.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


