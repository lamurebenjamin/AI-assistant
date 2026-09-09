# -*- coding: utf-8 -*-
"""Thread de requête d'inférence LLM avec streaming SSE et support agentique."""

import base64
import json
import logging
import re
from typing import List, Optional

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from core.skill_manager import SkillError
from src.config.schema import HTTP_TIMEOUT, LOGGER
from src.llm.agent import extract_user_request_text, messages_have_audio, requires_tool_call
from src.llm.response_parser import clean_chunk


class LlamaThread(QThread):
    """Thread de génération llama.cpp avec streaming et suivi des tools/skills."""

    new_text = pyqtSignal(str)
    tool_event = pyqtSignal(str, str, str)  # phase, nom, détail JSON/texte
    request_error = pyqtSignal(str, bool)

    MAX_TOOL_ROUNDS = 3

    def __init__(
        self,
        api_url: str,
        prompt: str,
        system_prompt: str,
        prefix: str,
        model: str,
        audio_data: Optional[bytes] = None,
        audio_format: Optional[str] = None,
        audio_language: str = "fr",
        vocabulary_prompt: str = "",
        skill_manager=None,
        enable_tools: bool = True,
    ):
        super().__init__()
        self.api_url = api_url
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.prefix = prefix
        self.model = model
        self.audio_data = audio_data
        self.audio_format = audio_format or "wav"
        self.audio_language = (audio_language or "fr").strip().lower()
        self.vocabulary_prompt = (vocabulary_prompt or "").strip()
        self.skill_manager = skill_manager
        self.enable_tools = bool(enable_tools and skill_manager is not None)
        self.tool_definitions = []
        if self.enable_tools:
            try:
                self.tool_definitions = skill_manager.describe_for_llm()
            except Exception:
                LOGGER.exception("Impossible de préparer les tools pour llama.cpp")
                self.tool_definitions = []
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    clean_chunk = staticmethod(clean_chunk)

    def _make_messages(self, user_content):
        return [
            {"role": "system", "content": f"{self.system_prompt.rstrip()}\n\n"},
            {"role": "user", "content": user_content},
        ]

    def _base_payload(
        self, messages: list, stream: bool = True, include_tools: bool = False, tool_choice: str = "auto"
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.1 if include_tools else 0.4,
            "top_p": 0.85,
            "top_k": 30,
            "min_p": 0.05,
            "repeat_penalty": 1.08,
            "repeat_last_n": 256,
            "max_tokens": 1024,
            "stop": ["<|end|>", "<end_of_turn>", "<|channel|>final"],
        }
        if include_tools and self.tool_definitions:
            payload["tools"] = self.tool_definitions
            payload["tool_choice"] = tool_choice
            payload["parallel_tool_calls"] = False
        return payload

    @staticmethod
    def _tool_call_from_delta(delta: dict, calls: list) -> list:
        """Fusionne les fragments SSE de tool_calls."""
        tool_calls = delta.get("tool_calls") or []
        for raw in tool_calls:
            index = raw.get("index", len(calls))
            try:
                index = int(index)
            except (TypeError, ValueError):
                index = len(calls)
            while len(calls) <= index:
                calls.append({
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                })
            current = calls[index]
            if raw.get("id"):
                current["id"] = raw["id"]
            if raw.get("type"):
                current["type"] = raw["type"]
            function = raw.get("function") or {}
            if function.get("name"):
                current["function"]["name"] += str(function["name"])
            if function.get("arguments"):
                current["function"]["arguments"] += str(function["arguments"])
        return calls

    def _execute_tool_calls(self, tool_calls: list) -> list:
        results = []
        for call in tool_calls:
            if self._stop_requested:
                break
            function = call.get("function") or {}
            name = str(function.get("name") or "").strip()
            arguments_text = function.get("arguments") or "{}"
            if not name:
                raise SkillError("Le modèle a demandé un outil sans nom.")
            try:
                arguments = json.loads(arguments_text)
            except json.JSONDecodeError as error:
                raise SkillError(
                    f"Arguments JSON invalides pour l'outil '{name}' : {error}"
                ) from error
            if not isinstance(arguments, dict):
                raise SkillError(f"Les arguments de '{name}' doivent être un objet JSON.")

            LOGGER.info("Tool call : %s(%s)", name, arguments)
            arguments_display = json.dumps(arguments, ensure_ascii=False, indent=2, default=str)
            self.tool_event.emit("appel", name, arguments_display)
            try:
                result = self.skill_manager.execute_tool(name, arguments)
                result_payload = {"success": True, "result": result}
                result_display = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                self.tool_event.emit("résultat", name, result_display)
            except Exception as error:
                LOGGER.exception("Erreur d'exécution du tool '%s'", name)
                error_detail = f"{type(error).__name__}: {error}"
                self.tool_event.emit("erreur", name, error_detail)
                result_payload = {
                    "success": False,
                    "error": error_detail,
                }

            try:
                serialized = json.dumps(result_payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                serialized = json.dumps({"success": True, "result": str(result_payload)}, ensure_ascii=False)

            results.append({
                "role": "tool",
                "tool_call_id": call.get("id") or f"call_{len(results)+1}",
                "content": serialized,
            })
        return results

    def _stream_request(self, messages: list, include_tools: bool = False, tool_choice: str = "auto") -> tuple:
        payload = self._base_payload(
            messages,
            stream=True,
            include_tools=include_tools,
            tool_choice=tool_choice,
        )
        received_text = []
        tool_calls = []
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        with requests.post(
            self.api_url,
            json=payload,
            stream=True,
            timeout=HTTP_TIMEOUT,
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
                    LOGGER.debug("Fragment SSE ignoré : %r", line[:300])
                    continue

                choices = data.get("choices") or []
                choice = choices[0] if choices else {}
                delta = choice.get("delta") or {}
                message = choice.get("message") or {}

                self._tool_call_from_delta(delta, tool_calls)
                if message.get("tool_calls"):
                    tool_calls = message.get("tool_calls") or tool_calls

                content = (
                    delta.get("content")
                    or delta.get("reasoning_content")
                    or choice.get("text")
                    or message.get("content")
                    or data.get("content")
                )
                if isinstance(content, list):
                    content = "".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    )
                content = self.clean_chunk(content or "")
                if content:
                    received_text.append(content)
                    self.new_text.emit(content)

            return "".join(received_text), tool_calls

    _messages_have_audio = staticmethod(messages_have_audio)
    _message_text = staticmethod(extract_user_request_text)
    _requires_tool_call = staticmethod(requires_tool_call)

    def _run_agent(self, messages: list) -> str:
        must_use_tool = self._requires_tool_call(messages)
        tool_was_called = False

        if must_use_tool:
            messages = list(messages)
            messages[0] = dict(messages[0])
            messages[0]["content"] = (
                str(messages[0].get("content") or "")
                + "\n\nRÈGLE D'EXÉCUTION PRIORITAIRE : la demande exige une action réelle. "
                  "Tu dois appeler un outil disponible. Il est interdit de répondre que tu ne "
                  "peux pas créer, enregistrer ou modifier le fichier, et il est interdit de "
                  "remplacer l'action par des instructions manuelles."
            )

        for _round in range(self.MAX_TOOL_ROUNDS):
            if self._stop_requested:
                return ""

            choice = "required" if must_use_tool and not tool_was_called else "auto"
            text, tool_calls = self._stream_request(
                messages,
                include_tools=bool(self.tool_definitions),
                tool_choice=choice,
            )

            if not tool_calls:
                if must_use_tool and not tool_was_called:
                    raise SkillError(
                        "La demande nécessite un outil, mais le modèle n'a émis aucun tool_call. "
                        "Vérifiez la compatibilité tool-calling du modèle et du chat template llama.cpp."
                    )
                return text

            tool_was_called = True
            assistant_message = {
                "role": "assistant",
                "content": text or None,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_message)
            messages.extend(self._execute_tool_calls(tool_calls))

        raise SkillError(
            f"Nombre maximal d'étapes d'outils atteint ({self.MAX_TOOL_ROUNDS})."
        )

    def _run_plain_audio(self, user_content) -> str:
        text, _ = self._stream_request(self._make_messages(user_content), include_tools=False)
        return text

    def run(self):
        try:
            if self.audio_data is not None:
                try:
                    encoded_audio = base64.b64encode(self.audio_data).decode("ascii")
                except Exception as error:
                    self.request_error.emit(f"Erreur d'encodage Base64 : {error}", False)
                    return

                action_instruction = (
                    self.prefix.strip()
                    or "Traite cet enregistrement comme la demande de l'utilisateur."
                )
                language_instruction = (
                    "La langue parlée attendue est le français. "
                    if self.audio_language == "fr"
                    else f"La langue parlée attendue est : {self.audio_language}. "
                )
                vocabulary_instruction = (
                    f"Contexte lexical à privilégier si l'audio le confirme : {self.vocabulary_prompt} "
                    if self.vocabulary_prompt
                    else ""
                )
                instruction = (
                    language_instruction
                    + vocabulary_instruction
                    + "Transcris d'abord fidèlement les paroles de l'utilisateur, puis exécute la demande. "
                    "Reponds obligatoirement sous cette forme exacte : "
                    "<transcript>transcription integrale</transcript><answer>reponse finale</answer>. "
                    "N'ajoute aucun texte hors de ces balises. Instruction de l'action : "
                    + action_instruction
                )
                user_content = [
                    {"type": "text", "text": instruction},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": encoded_audio,
                            "format": self.audio_format,
                        },
                    },
                ]
                messages = self._make_messages(user_content)
                if self.enable_tools and self.tool_definitions:
                    final_text = self._run_agent(messages)
                else:
                    final_text = self._run_plain_audio(user_content)
            else:
                user_content = "\n".join(
                    part for part in (self.prefix.strip(), self.prompt.strip()) if part
                )
                messages = self._make_messages(user_content)
                if self.enable_tools and self.tool_definitions:
                    final_text = self._run_agent(messages)
                else:
                    final_text, _ = self._stream_request(messages, include_tools=False)

            if self._stop_requested:
                return
            if not final_text:
                self.request_error.emit(
                    "Le serveur a terminé la requête sans envoyer de texte exploitable. "
                    "Consultez llama-server.log pour vérifier le format de la réponse.",
                    False,
                )
        except requests.exceptions.RequestException as error:
            detail = str(error)
            response = getattr(error, "response", None)
            if response is not None:
                try:
                    detail = response.text[:1600] or detail
                except Exception:
                    pass
            lowered = detail.lower()
            incompatible = self.audio_data is not None and any(
                term in lowered
                for term in (
                    "input_audio",
                    "audio",
                    "multimodal",
                    "unsupported content",
                    "invalid content type",
                    "image only",
                )
            )
            message = (
                "Le modèle ou le serveur llama.cpp actuellement chargé ne prend pas en charge les entrées audio directes."
                if incompatible
                else f"Erreur réseau : {detail}"
            )
            self.request_error.emit(message, incompatible)
        except (ValueError, TypeError, KeyError, SkillError, json.JSONDecodeError) as error:
            self.request_error.emit(f"Erreur agent/skill : {error}", False)
        except Exception as error:
            LOGGER.exception("Erreur inattendue dans LlamaThread")
            self.request_error.emit(
                f"Erreur inattendue : {type(error).__name__}: {error}", False
            )
