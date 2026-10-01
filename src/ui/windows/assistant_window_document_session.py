"""Cycle des requetes et sources documentaires."""

import os
import re

from src.config.schema import LOGGER
from src.documents.pdf_utils import open_pdf_at_page as _open_pdf_at_page
from src.documents.thread import DocumentAnalysisThread


def start_document_analysis(self, paths, question, audio_data=None, forced_tool=None, *, server_manager):
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
        auth_token=server_manager.auth_token,
    )
    self.document_thread.new_text.connect(self.update_document_text)
    self.document_thread.thinking_text.connect(self.update_document_thinking)
    self.document_thread.tool_event.connect(self.update_document_tool_event)
    self.document_thread.request_error.connect(self.handle_document_error)
    self.document_thread.finished.connect(self.on_document_finished)
    self.document_thread.start()


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
