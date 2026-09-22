"""Composer input and audio orchestration for DocumentDialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from src.audio.recorder import AudioRecorderThread


class DocumentComposerController:
    """Owns input state while keeping DocumentDialog's public callbacks stable."""

    def __init__(self, dialog):
        self.dialog = dialog

    def _update_question_height(self):
        """Agrandit la saisie jusqu'à trois lignes, puis active son défilement."""
        dialog = self.dialog
        document = dialog.question.document()
        document.setTextWidth(max(40, dialog.question.viewport().width()))
        line_height = max(14, dialog.question.fontMetrics().lineSpacing())
        minimum_height = 30
        maximum_height = minimum_height + 2 * line_height
        content_height = int(document.size().height()) + 8
        target_height = max(minimum_height, min(maximum_height, content_height))
        previous_height = getattr(self, "_question_height", minimum_height)
        dialog._question_height = target_height
        dialog.question.setFixedHeight(target_height)
        dialog.question.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if content_height > maximum_height else Qt.ScrollBarAlwaysOff
        )
        if content_height > maximum_height:
            bar = dialog.question.verticalScrollBar()
            bar.setValue(bar.maximum())
        # Une suppression ne doit pas redimensionner la fenêtre ni déplacer le
        # viewport de la conversation. La scrollbar du flux absorbe le contenu
        # qui dépasse la hauteur disponible. On ne redimensionne que lors d'une
        # croissance réelle du champ de saisie.
        if target_height > previous_height:
            dialog._update_height()

    def _update_send_visibility(self):
        """Affiche une seule action adaptée à l'état du compositeur."""
        dialog = self.dialog
        if dialog.streaming_response_active:
            dialog.mic.hide()
            dialog.send.hide()
            dialog.stop_generation_button.show()
            return
        dialog.stop_generation_button.hide()
        if dialog.is_recording:
            dialog.mic.show()
            dialog.send.hide()
            return
        has_text = bool(dialog.question.toPlainText().strip())
        dialog.mic.setVisible(not has_text)
        dialog.send.setVisible(has_text)

    def _stop_llm_generation(self):
        """Arrête réellement la génération sans afficher de message intermédiaire."""
        dialog = self.dialog
        if not dialog.streaming_response_active:
            return
        dialog.stop_generation_button.setEnabled(False)
        thread = dialog.host.document_thread if dialog.host is not None else None
        if thread is not None and thread.isRunning():
            thread.stop()
        else:
            dialog.finish_response()

    def _ask_text(self):
        dialog = self.dialog
        question = dialog.question.toPlainText().strip()
        forced_tool = getattr(dialog, "_pending_forced_tool", None)
        if dialog._pending_skill_tag:
            question = question.replace("\uFFFC", "")
            question = question.replace(str(dialog._pending_skill_tag.get("title", "")), "", 1).strip()
        if not question and not forced_tool:
            dialog.status.setText("Saisissez une question ou utilisez le microphone")
            return
        dialog._pending_forced_tool = None
        skill_tag = dialog._pending_skill_tag
        dialog._clear_skill_tag()
        documents, attachments_html = dialog._take_current_attachments()
        dialog.begin_response(question, attachments_html, skill_tag, documents)
        dialog.question.clear()
        dialog.ask_requested.emit(documents, question, None, forced_tool)
        dialog._prompt_history_index = None
        dialog._prompt_history_draft = ""

    def _prompt_history(self):
        dialog = self.dialog
        return [
            str(turn.get("question", "") or "")
            for turn in dialog.turns
            if str(turn.get("question", "") or "").strip()
            and str(turn.get("question", "") or "").strip() != "Question audio"
        ]

    def _reset_prompt_history_navigation(self):
        dialog = self.dialog
        if not dialog.question.signalsBlocked():
            dialog._prompt_history_index = None
            dialog._prompt_history_draft = ""

    def _navigate_prompt_history(self, direction: int):
        """Navigue dans les prompts de la session comme l'historique d'un terminal."""
        dialog = self.dialog
        history = self._prompt_history()
        if not history:
            return

        if dialog._prompt_history_index is None:
            dialog._prompt_history_draft = dialog.question.toPlainText()
            dialog._prompt_history_index = len(history)

        next_index = max(
            0, min(len(history), dialog._prompt_history_index + direction)
        )
        if next_index == dialog._prompt_history_index:
            return
        dialog._prompt_history_index = next_index
        text = (
            dialog._prompt_history_draft
            if next_index == len(history)
            else history[next_index]
        )
        dialog.question.blockSignals(True)
        dialog.question.setPlainText(text)
        cursor = dialog.question.textCursor()
        cursor.movePosition(QTextCursor.End)
        dialog.question.setTextCursor(cursor)
        dialog.question.blockSignals(False)
        dialog.question.setFocus(Qt.OtherFocusReason)
    def _set_inline_recording_visual(self,active):
        dialog = self.dialog
        dialog.question.setVisible(not active)
        # Un clic pendant la dictée termine l'enregistrement puis envoie
        # l'audio. L'icône Envoyer correspond donc à l'action réelle.
        dialog.mic.kind="send" if active else "mic"
        dialog.mic.update()
        dialog.audio_bars.start() if active else dialog.audio_bars.stop()
        dialog._update_send_visibility()
        dialog._update_height()
    def _toggle_microphone(self):
        dialog = self.dialog
        if dialog.is_recording:
            if dialog.audio_thread and dialog.audio_thread.isRunning():dialog.audio_thread.stop_recording()
            dialog.status.setText("Traitement de la question audio..."); return
        voice=dialog.host.config.get("voice_input",{}) if dialog.host else {}; dialog.is_recording=True; dialog._set_inline_recording_visual(True)
        device=dialog.host._selected_voice_device() if dialog.host else None
        dialog.audio_thread=AudioRecorderThread(device,voice.get("sample_rate",16000),voice.get("maximum_duration",60.0),release_tail_ms=voice.get("release_tail_ms",700),microphone_gain=voice.get("microphone_gain",2.0),parent=dialog)
        dialog.audio_thread.level_changed.connect(dialog.audio_bars.set_level); dialog.audio_thread.recorded.connect(dialog._audio_ready); dialog.audio_thread.error.connect(dialog._audio_error); dialog.audio_thread.start()
    def _audio_ready(self, data, duration, rms):
        dialog = self.dialog
        dialog.is_recording = False
        dialog.audio_thread = None
        dialog._set_inline_recording_visual(False)
        if not data or duration < 0.3:
            dialog.status.setText("Aucun son détecté")
            return
        documents, attachments_html = dialog._take_current_attachments()
        dialog.begin_response("Question audio", attachments_html, documents=documents)
        dialog.ask_requested.emit(documents, "", data, None)
    def _audio_error(self, message):
        dialog = self.dialog
        dialog.is_recording = False
        dialog.audio_thread = None
        dialog._set_inline_recording_visual(False)
        dialog.status.setText(message)
