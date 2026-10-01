"""Execution et suivi des requetes du modele local."""

import html
import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from src.llm.client import LlamaThread


def trigger_action(self, index, user_text_override=None, audio_data=None, audio_format=None):
    if not 0 <= index < len(self.config["actions"]): return
    if audio_data is not None:
        self.selected_text = ""
        self.execute_action(self.config["actions"][index], audio_data=audio_data, audio_format=audio_format)
        return
    self.selected_text = user_text_override if user_text_override is not None else self.get_selected_text()
    self.execute_action(self.config["actions"][index])


def execute_action(self, action_cfg, preserve_position=False, audio_data=None, audio_format=None, *, server_manager):
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
        auth_token=server_manager.auth_token,
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
