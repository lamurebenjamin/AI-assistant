"""Response lifecycle orchestration for DocumentDialog."""

import html
import os
import re
import time

from PySide6.QtCore import QTimer


class DocumentResponseController:
    """Owns response streaming state while preserving the dialog facade."""

    def __init__(self, dialog):
        self.dialog = dialog

    def begin_response(self, question, attachments_html="", skill_tag=None, documents=None):
        dialog = self.dialog
        dialog.streaming_response_active = True
        dialog.current_assistant_bubble = None
        document_count = len(documents or [])
        if document_count:
            extensions = {
                os.path.splitext(str(item.get("path", "")))[1].lower()
                for item in documents
                if isinstance(item, dict)
            }
            if extensions and extensions.issubset({".pdf"}):
                thinking_status = f"Analyse de {document_count} PDF…"
            elif extensions & {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
                thinking_status = f"Lecture de {document_count} document(s) et image(s)…"
            else:
                thinking_status = f"Lecture de {document_count} document(s)…"
        else:
            thinking_status = "Analyse de la demande"
        dialog.turns.append({
            "question": question,
            "answer": "",
            "thinking": "",
            "timeline": [],
            "sources_html": "",
            "attachments_html": attachments_html,
            "skill_tag": skill_tag,
            "loading": True,
            "thinking_status": thinking_status,
            "thinking_start_time": None,
            "thinking_duration": None,
            "timestamp": time.strftime("%H:%M"),
        })
        dialog.current_turn_index = len(dialog.turns) - 1
        dialog.response.show()
        dialog._render_conversation()
        dialog.stop_generation_button.setEnabled(True)
        dialog._update_send_visibility()

    def append_thinking(self, text):
        dialog = self.dialog
        if dialog.current_turn_index < 0 or not text:
            return
        turn = dialog.turns[dialog.current_turn_index]
        turn["thinking"] = turn.get("thinking", "") + text
        turn["thinking"] = re.sub(
            r"(?im)^\s*thinking\s+process\s*:\s*",
            "",
            turn["thinking"],
        )
        timeline = turn.setdefault("timeline", [])
        if timeline and timeline[-1].get("type") == "thinking":
            timeline[-1]["text"] = turn["thinking"]
        else:
            timeline.append({"type": "thinking", "text": turn["thinking"]})
            dialog.current_thinking_widget = None
        if not turn.get("thinking_start_time"):
            turn["thinking_start_time"] = time.time()
        turn["thinking_status"] = "Réflexion en cours…"
        if dialog.current_thinking_widget is not None:
            try:
                dialog.current_thinking_widget.set_text(turn["thinking"])
                dialog.pending_stream_render = True
            except RuntimeError:
                dialog.current_thinking_widget = None
        if dialog.current_thinking_widget is None:
            dialog.pending_stream_render = True
        if not dialog.stream_render_timer.isActive():
            dialog.stream_render_timer.start()

    def append_response(self,text):
        dialog = self.dialog
        if dialog.current_turn_index < 0:
            return
        turn = dialog.turns[dialog.current_turn_index]
        if not turn.get("response_start_time"):
            turn["response_start_time"] = time.time()
        turn["answer"] += text
        timeline = turn.setdefault("timeline", [])
        if timeline and timeline[-1].get("type") == "response":
            timeline[-1]["text"] += text
        else:
            timeline.append({"type": "response", "text": text})
            dialog.current_assistant_bubble = None
        turn["thinking_status"] = "Rédaction de la réponse…"
        if dialog.current_thinking_widget is not None:
            thinking_start = turn.get("thinking_start_time")
            duration = (
                max(0, time.time() - thinking_start)
                if thinking_start
                else 0
            )
            turn["thinking_duration"] = duration
            dialog.current_thinking_widget.finish(duration)
        # Dès le premier fragment, le statut de réflexion disparaît. Le rendu est ensuite
        # limité à environ 22 mises à jour par seconde pour supprimer scintillement,
        # sauts de largeur et pertes temporaires de la barre de défilement.
        turn["loading"] = False
        dialog.pending_stream_render = True
        if not dialog.stream_render_timer.isActive():
            dialog.stream_render_timer.start()

    def _flush_stream_render(self):
        dialog = self.dialog
        if not dialog.pending_stream_render:
            return
        dialog.pending_stream_render = False
        if dialog.current_turn_index < 0:
            return
        turn = dialog.turns[dialog.current_turn_index]
        # Le raisonnement est déjà rendu dans son widget dédié par
        # append_thinking(). Ne reconstruis pas toute la conversation pendant
        # son streaming : cela détruit/recrée les widgets et provoque un
        # clignotement visible.
        if (
            turn.get("timeline")
            and turn["timeline"][-1].get("type") == "thinking"
            and not turn.get("answer")
            and dialog.current_thinking_widget is not None
        ):
            try:
                if dialog.current_thinking_widget.parent() is not None:
                    dialog._refresh_stream_view()
                    return
            except RuntimeError:
                dialog.current_thinking_widget = None
        answer = dialog._answer_without_sources(turn.get("answer", ""))
        rendered = (
            dialog.host.markdown_to_html(answer, dialog.FONT_SIZE_OFFSET)
            if dialog.host is not None
            else html.escape(answer).replace("\n", "<br>")
        )
        try:
            bubble_is_valid = (
                dialog.current_assistant_bubble is not None
                and dialog.current_assistant_bubble.parent() is not None
            )
        except RuntimeError:
            bubble_is_valid = False
        if not bubble_is_valid:
            # Premier fragment uniquement : remplace les points par la bulle.
            dialog._render_conversation()
        else:
            # Fragments suivants : mise à jour du QTextBrowser existant, sans
            # supprimer ni recréer les widgets de la conversation.
            dialog.current_assistant_bubble.set_html(
                rendered + turn.get("sources_html", "")
            )
            QTimer.singleShot(0, dialog._refresh_stream_view)

    def _on_tool_widget_toggled(self):
        dialog = self.dialog
        dialog._allow_shrink_height = True
        scroll_bar = dialog.response.verticalScrollBar()
        previous_value = scroll_bar.value()
        sender = dialog.sender()
        if sender is not None:
            parent = sender.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().activate()
        dialog._sync_conversation_widget_height()
        dialog.response.widget().adjustSize()
        dialog._update_height()
        dialog._update_turn_navigation_visibility()
        # Le repli/dépli d'une étape ne doit pas déplacer l'utilisateur dans
        # l'historique : restaurer la position après la mise à jour des layouts.
        QTimer.singleShot(
            0,
            lambda: dialog._finish_toggle_layout(scroll_bar, previous_value),
        )

    def _finish_toggle_layout(self, scroll_bar, previous_value):
        dialog = self.dialog
        dialog._allow_shrink_height = True
        dialog._sync_conversation_widget_height()
        dialog.response.widget().adjustSize()
        dialog._update_height()
        dialog._update_response_scroll_policy()
        scroll_bar.setValue(min(previous_value, scroll_bar.maximum()))
        dialog._update_turn_navigation_visibility()

    def record_tool_event(self, phase: str, name: str, detail: str):
        dialog = self.dialog
        """Enregistre et met à jour l'événement d'outil dans la conversation."""
        if dialog.current_turn_index < 0 and dialog.turns:
            dialog.current_turn_index = len(dialog.turns) - 1
        if dialog.current_turn_index < 0:
            return
        turn = dialog.turns[dialog.current_turn_index]
        tools = turn.setdefault("tools", [])
        tool_icon = None
        tool_skill = "ftnc"
        try:
            tool_info = dialog.skill_manager.get_tool(name)
            tool_skill = tool_info.get("skill", "ftnc")
            tool_icon = dialog.skill_manager.get_skill_icon(tool_skill)
        except (KeyError, AttributeError):
            tool_icon = None

        if phase == "appel":
            timeline = turn.setdefault("timeline", [])
            tool_status = {
                "read_pdf": "Analyse du PDF…",
                "extract_pdf_text": "Extraction du texte du PDF…",
                "search_pdf": "Recherche dans le PDF…",
                "create_pdf": "Création du document PDF…",
                "create_docx": "Création du document Word…",
                "create_excel": "Création du classeur Excel…",
                "create_pptx": "Création de la présentation PowerPoint…",
            }
            turn["thinking_status"] = tool_status.get(
                name,
                f"Exécution de « {name} »…",
            )
            if not turn.get("tool_start_time"):
                turn["tool_start_time"] = time.time()
            tool_entry = {
                "name": name,
                "status": "running",
                "arguments": detail or "",
                "result": "",
                "expanded": False,
                "icon": tool_icon,
                "skill_name": tool_skill,
                "tool_name": name,
            }
            tools.append(tool_entry)
            if not timeline or timeline[-1].get("type") != "tools":
                timeline.append({"type": "tools", "tools": []})
            timeline[-1]["tools"].append(tool_entry)
        elif phase == "résultat":
            turn["thinking_status"] = f"Traitement du résultat de « {name} »…"
            for t in reversed(tools):
                if t.get("name") == name or t.get("status") == "running":
                    t["status"] = "done"
                    if detail:
                        t["result"] = detail
                    break
            for event in reversed(turn.get("timeline", [])):
                if event.get("type") == "tools":
                    for entry in reversed(event.get("tools", [])):
                        if entry.get("name") == name or entry.get("status") == "running":
                            entry["status"] = "done"
                            if detail:
                                entry["result"] = detail
                            break
                    break
            else:
                tools.append({
                    "name": name,
                    "status": "done",
                    "arguments": "",
                    "result": detail or "",
                    "expanded": False,
                    "icon": tool_icon,
                    "skill_name": tool_skill,
                    "tool_name": name,
                })
            if tools and not any(t.get("status") == "running" for t in tools):
                turn["tool_end_time"] = time.time()
                turn["tools_collapsed"] = True
        elif phase == "erreur":
            turn["thinking_status"] = f"Analyse de l’erreur de « {name} »…"
            for t in reversed(tools):
                if t.get("name") == name or t.get("status") == "running":
                    t["status"] = "error"
                    if detail:
                        t["result"] = detail
                    break
            else:
                tools.append({
                    "name": name,
                    "status": "error",
                    "arguments": "",
                    "result": detail or "",
                    "expanded": False,
                    "icon": tool_icon,
                })
            if tools and not any(t.get("status") == "running" for t in tools):
                turn["tool_end_time"] = time.time()
                turn["tools_collapsed"] = True

        dialog._render_conversation()

    def finish_response(self):
        dialog = self.dialog
        dialog.streaming_response_active = False
        dialog.stream_render_timer.stop()
        dialog.pending_stream_render = False
        if dialog.current_turn_index >= 0:
            dialog.turns[dialog.current_turn_index]["loading"] = False
            dialog.turns[dialog.current_turn_index]["thinking_status"] = ""
            turn = dialog.turns[dialog.current_turn_index]
            if turn.get("thinking_start_time") and turn.get("thinking_duration") is None:
                turn["thinking_duration"] = max(
                    0, time.time() - turn["thinking_start_time"]
                )
            for t in dialog.turns[dialog.current_turn_index].get("tools", []):
                if t.get("status") == "running":
                    t["status"] = "done"
            if dialog.turns[dialog.current_turn_index].get("tools"):
                dialog.turns[dialog.current_turn_index]["tool_end_time"] = time.time()
                dialog.turns[dialog.current_turn_index]["tools_collapsed"] = True
        dialog.status.clear()
        dialog.status.hide()
        dialog.stop_generation_button.setEnabled(True)
        dialog._update_send_visibility()
        # Autorise _update_height à recalculer librement la vraie hauteur du contenu final,
        # sans être bloqué par la valeur maximale imposée pendant le streaming.
        dialog._allow_shrink_height = True
        dialog.expanded_height = dialog.MIN_HEIGHT
        dialog._render_conversation()
        # Le viewport peut encore récupérer la largeur libérée par la scrollbar
        # après le rendu final. Recalculer les bulles dans le tour d'événements
        # suivant évite de conserver la largeur transitoire du streaming.
        QTimer.singleShot(0, dialog._refresh_conversation_widths)
    def show_error(self,message):
        dialog = self.dialog
        dialog.streaming_response_active = False
        if dialog.current_turn_index>=0:
            dialog.turns[dialog.current_turn_index]["loading"] = False
            dialog.turns[dialog.current_turn_index]["error"] = str(message or "Erreur inconnue.")
        dialog.status.setText("Erreur d'analyse")
        dialog.stop_generation_button.setEnabled(True)
        dialog._update_send_visibility()
        dialog._render_conversation()

