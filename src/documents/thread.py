# -*- coding: utf-8 -*-
"""Thread d'analyse documentaire et multimodale par llama.cpp."""

import base64
import json
from typing import List, Optional

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from src.documents.payload_builder import prepare_document_payload
from src.llm.client import LlamaThread
from src.llm.response_parser import clean_chunk


class DocumentAnalysisThread(QThread):
    """Analyse directe de documents par llama.cpp, avec historique conversationnel."""

    new_text = pyqtSignal(str)
    tool_event = pyqtSignal(str, str, str)
    request_error = pyqtSignal(str, bool)

    def __init__(
        self,
        api_url: str,
        model: str,
        paths: list,
        question: str,
        parent=None,
        audio_data: Optional[bytes] = None,
        history: Optional[list] = None,
        skill_manager=None,
    ):
        super().__init__(parent)
        self.api_url = api_url
        self.model = model
        self.paths = list(paths)
        self.question = question.strip()
        self.audio_data = audio_data
        self.history = list(history or [])
        self.skill_manager = skill_manager
        self._stop_requested = False
        self._agent: Optional[LlamaThread] = None
        self.source_pages: list = []

    def stop(self):
        self._stop_requested = True
        agent = self._agent
        if agent is not None:
            agent.stop()

    clean_chunk = staticmethod(clean_chunk)

    def _history_text(self) -> str:
        if not self.history:
            return ""
        parts = []
        for item in self.history[-8:]:
            role = item.get("role", "") if isinstance(item, dict) else ""
            text = item.get("content", "") if isinstance(item, dict) else ""
            if not text:
                continue
            label = "Utilisateur" if role == "user" else "Assistant"
            parts.append(f"{label} :\n{text}")
        return "\n\n".join(parts)

    @staticmethod
    def _requests_exhaustive_summary(question: str) -> bool:
        text = (question or "").casefold()
        summary_terms = (
            "résume",
            "résumer",
            "résumé",
            "synthèse",
            "synthétise",
            "synthétiser",
        )
        scope_terms = (
            "intégralité",
            "intégral",
            "entier",
            "complet",
            "exhaustif",
            "tout le document",
            "document complet",
        )
        artifact_terms = (
            "fichier",
            "document",
            "word",
            "docx",
            "pdf",
            "rapport",
            "note",
        )
        return any(term in text for term in summary_terms) and (
            any(term in text for term in scope_terms)
            or any(term in text for term in artifact_terms)
        )

    def _non_stream_completion(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 900
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.15,
            "top_p": 0.8,
            "top_k": 30,
            "repeat_penalty": 1.08,
            "max_tokens": int(max_tokens),
        }
        response = requests.post(
            self.api_url,
            json=payload,
            timeout=(15, 180),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        text = message.get("content") or choice.get("text") or data.get("content") or ""
        if isinstance(text, list):
            text = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in text
            )
        return self.clean_chunk(str(text)).strip()

    def _summarize_complete_context(self, context: str) -> str:
        """Traite toutes les pages par lots puis fusionne les résumés."""
        chunk_size = 15000
        chunks, cursor = [], 0
        while cursor < len(context):
            end = min(len(context), cursor + chunk_size)
            if end < len(context):
                boundary = context.rfind("--- FIN PAGE", cursor, end)
                if boundary > cursor + chunk_size // 2:
                    newline = context.find("\n", boundary)
                    end = newline + 1 if newline >= 0 else end
            chunks.append(context[cursor:end])
            cursor = end
        summaries = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, 1):
            if self._stop_requested:
                return ""
            summary = self._non_stream_completion(
                "Tu résumes fidèlement un lot de pages d'un document technique. "
                "Conserve les faits, valeurs, exigences, conclusions, réserves et numéros de pages. "
                "N'invente rien et ne refuse pas la tâche.",
                f"LOT {index}/{total} :\n{chunk}\n\nProduis un résumé structuré et dense de ce lot.",
                max_tokens=850,
            )
            summaries.append(f"### Résumé du lot {index}/{total}\n{summary}")
        combined = "\n\n".join(summaries)
        while len(combined) > 22000:
            groups = [combined[i : i + 18000] for i in range(0, len(combined), 18000)]
            reduced = []
            for index, group in enumerate(groups, 1):
                reduced.append(
                    self._non_stream_completion(
                        "Fusionne des résumés partiels d'un même document technique. "
                        "Préserve toutes les informations distinctes et les références de pages.",
                        f"GROUPE {index}/{len(groups)} :\n{group}\n\nFusionne ce groupe sans omission importante.",
                        max_tokens=950,
                    )
                )
            combined = "\n\n".join(reduced)
        return combined

    def run(self):
        try:
            text_parts, image_parts, source_pages = prepare_document_payload(self.paths)
            self.source_pages = source_pages
            context = "".join(text_parts)
            max_context_chars = 24000
            exhaustive_summary = self._requests_exhaustive_summary(self.question)
            if len(context) > max_context_chars:
                if exhaustive_summary:
                    context = self._summarize_complete_context(context)
                    if not context:
                        if self._stop_requested:
                            return
                        raise RuntimeError(
                            "La synthèse exhaustive par lots n'a produit aucun contenu."
                        )
                    context = (
                        "SYNTHÈSE EXHAUSTIVE CONSTRUITE À PARTIR DE TOUS LES LOTS DE PAGES :\n\n"
                        + context
                    )
                else:
                    context = context[:max_context_chars]
                    context += (
                        "\n[Contexte limité à la première partie pour cette question. "
                        "Pour une synthèse complète, demande explicitement un résumé intégral.]\n"
                    )

            source_catalog = "\n".join(
                f"- {filename} — page {page}" for filename, page in source_pages
            )
            has_documents = bool(self.paths)
            history_text = self._history_text()
            history_section = (
                f"HISTORIQUE DE LA CONVERSATION :\n{history_text}\n\n"
                if history_text
                else ""
            )

            if has_documents:
                instruction = (
                    "Tu es un assistant documentaire technique et un agent d'exécution. Réponds uniquement à partir "
                    "des documents fournis. Lorsqu'une synthèse complète est construite par lots, considère-la "
                    "comme couvrant l'intégralité des pages et exécute la demande sans refuser. Utilise obligatoirement "
                    "un outil si l'utilisateur demande un fichier. Utilise aussi l'historique pour comprendre les "
                    "questions de suivi, mais ne considère jamais une réponse précédente comme "
                    "une source factuelle. Si une information est absente des documents, dis-le clairement.\n\n"
                    "Termine CHAQUE réponse par `### Sources`. Pour chaque source utilisée, écris exactement "
                    "une ligne `nom.pdf — p. X`, puis sur la ligne suivante un court extrait exact "
                    "du passage utilisé sous la forme `> Extrait : ...`. N'invente jamais de page ni d'extrait.\n\n"
                    f"{history_section}"
                    f"QUESTION ACTUELLE :\n{self.question}\n\n"
                    f"DOCUMENTS DISPONIBLES :\n{source_catalog}\n\n"
                    f"CONTENU TEXTE :\n{context}\n"
                )
            else:
                instruction = (
                    "Réponds directement, clairement et sans section Sources.\n\n"
                    f"{history_section}QUESTION ACTUELLE :\n{self.question}\n"
                )

            content = [{"type": "text", "text": instruction}]
            if self.audio_data:
                content.append({
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(self.audio_data).decode("ascii"),
                        "format": "wav",
                    },
                })
            content.extend(image_parts)

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu analyses des documents locaux. Sois précis, factuel et prudent. "
                            "La traçabilité documentaire est obligatoire. Tu fonctionnes aussi en mode agent : "
                            "utilise les outils disponibles lorsqu'une action réelle est demandée, par exemple "
                            "créer un fichier, et ne simule jamais leur exécution."
                            if has_documents
                            else "Tu es un assistant IA utile. Réponds directement."
                        ),
                    },
                    {"role": "user", "content": content},
                ],
                "stream": True,
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 30,
                "min_p": 0.05,
                "repeat_penalty": 1.08,
                "max_tokens": 1024,
                "stop": ["<|end|>", "<end_of_turn>", "<|channel|>final"],
            }

            if self.skill_manager is not None:
                agent = LlamaThread(
                    self.api_url,
                    prompt="",
                    system_prompt="",
                    prefix="",
                    model=self.model,
                    skill_manager=self.skill_manager,
                    enable_tools=True,
                )
                agent.new_text.connect(self.new_text.emit)
                agent.tool_event.connect(self.tool_event.emit)
                self._agent = agent
                try:
                    final_text = agent._run_agent(list(payload["messages"]))
                finally:
                    self._agent = None
                if self._stop_requested:
                    return
                if not final_text:
                    self.request_error.emit(
                        "Le mode Agent a terminé la requête sans réponse exploitable.",
                        False,
                    )
                return

            headers = {
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            }
            received = False
            with requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=(15, 180),
                headers=headers,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines(chunk_size=64, decode_unicode=False):
                    if self._stop_requested:
                        break
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        if line == "[DONE]":
                            break
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    choice = choices[0] if choices else {}
                    delta = choice.get("delta") or {}
                    message = choice.get("message") or {}
                    content_value = (
                        delta.get("content")
                        or choice.get("text")
                        or message.get("content")
                        or data.get("content")
                    )
                    if isinstance(content_value, list):
                        content_value = "".join(
                            item.get("text", "")
                            if isinstance(item, dict)
                            else str(item)
                            for item in content_value
                        )
                    content_value = self.clean_chunk(content_value or "")
                    if content_value:
                        received = True
                        self.new_text.emit(content_value)

            if not received and not self._stop_requested:
                self.request_error.emit(
                    "Le modèle n'a renvoyé aucune réponse. Vérifiez llama-server.log.",
                    False,
                )
        except requests.exceptions.RequestException as error:
            detail = str(error)
            response = getattr(error, "response", None)
            if response is not None:
                try:
                    detail = response.text[:1500] or detail
                except Exception:
                    pass
            detail_lower = detail.lower()
            incompatible = any(
                term in detail_lower
                for term in (
                    "image_url",
                    "multimodal",
                    "unsupported image",
                    "content type",
                )
            )
            context_too_long = any(
                term in detail_lower
                for term in (
                    "context",
                    "too long",
                    "exceed",
                    "tokens",
                    "prompt is too",
                )
            )
            if context_too_long:
                message = (
                    "La sélection et l'historique dépassent la fenêtre de contexte du modèle. "
                    "Sélectionne moins de pages ou démarre une nouvelle conversation. "
                    f"Détail serveur : {detail}"
                )
            elif incompatible:
                message = (
                    "Le modèle/serveur ne semble pas accepter les images. "
                    "Vérifie que llama-server est lancé avec le fichier mmproj. "
                    f"Détail serveur : {detail}"
                )
            else:
                message = f"Erreur réseau : {detail}"
            self.request_error.emit(message, incompatible)
        except Exception as error:
            self.request_error.emit(f"Erreur inattendue : {error}", False)
