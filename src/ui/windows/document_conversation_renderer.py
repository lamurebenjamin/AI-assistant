"""Conversation rendering and source capture composition for DocumentDialog."""

import base64
import html
import json
import os
import re
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

import src.ui.design_tokens as t
from src.ui.stylesheet import qss_transparent_surface
from src.ui.widgets.chat_bubble import ChatBubble
from src.ui.widgets.thinking_dots import ShimmerLabel
from src.ui.widgets.tool_call_widget import ThinkingGroupWidget, ToolExecutionGroupWidget
from src.ui.windows.document_source_renderer import DocumentSourceRenderer


class DocumentConversationRenderer:
    """Owns conversation widgets, viewport sizing, and source capture HTML."""

    def __init__(self, dialog):
        self.dialog = dialog
        self.source_renderer = DocumentSourceRenderer(dialog)

    def _clear_conversation_widgets(self):
        dialog = self.dialog
        while dialog.conversation_layout.count():
            item = dialog.conversation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _clear_turn_navigation(self):
        dialog = self.dialog
        while dialog.turn_navigation_layout.count():
            item = dialog.turn_navigation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _navigate_to_turn(self, turn_index):
        dialog = self.dialog
        return dialog.conversation_controller.navigate_to_turn(turn_index)

    def render(self):
        dialog = self.dialog
        dialog._clear_conversation_widgets()
        dialog._clear_turn_navigation()
        dialog._turn_rows = []
        dialog._turn_navigation_buttons = []
        dialog.current_assistant_bubble = None
        dialog.current_thinking_widget = None
        if not dialog.turns:
            dialog.response.hide()
            dialog.response_holder.hide()
            return
        dialog.response_holder.show()
        for turn_index, turn in enumerate(dialog.turns):
            button = QPushButton("•", dialog.turn_navigation)
            button.setObjectName("TurnNavigationDot")
            button.setCheckable(True)
            button.setChecked(turn_index == dialog.current_turn_index)
            button.setFixedSize(
                14 if turn_index == dialog.current_turn_index else 8,
                14 if turn_index == dialog.current_turn_index else 8,
            )
            button.setToolTip("")
            button.clicked.connect(
                lambda checked, index=turn_index: dialog._navigate_to_turn(index)
            )
            dialog.turn_navigation_layout.addWidget(
                button,
                0,
                Qt.AlignHCenter | Qt.AlignVCenter,
            )
            dialog._turn_navigation_buttons.append(button)
        dialog.turn_navigation.setFixedHeight(
            max(24, dialog.turn_navigation_layout.sizeHint().height() + 8)
        )
        viewport_width = dialog.response.viewport().width()
        if viewport_width <= 150:
            viewport_width = dialog.width() - 32
        # Le viewport exclut déjà la largeur de la scrollbar verticale lorsqu'elle
        # est visible. La soustraire ici une seconde fois crée un vide à droite.
        # viewport_width correspond uniquement à la zone scrollable, la colonne
        # de navigation étant désormais fixe à côté du QScrollArea.
        available = max(160, viewport_width)
        bubble_width = max(120, available - 16)
        # La bulle peut occuper 80 % de la conversation, laissant 20 % à droite.
        user_bubble_width = max(120, available - 16)
        for turn_index, turn in enumerate(dialog.turns):
            raw_question = turn.get("question", "")
            if raw_question == "Question audio":
                # Conserve dans l'historique le visuel des barres qui défilait
                # pendant la dictée, plutôt qu'une icône de microphone.
                bars_width, bars_height = 78, 28
                pix = QPixmap(bars_width, bars_height)
                pix.fill(Qt.transparent)
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(Qt.NoPen)
                levels = (0.18, 0.38, 0.68, 0.42, 0.82, 0.55, 0.31, 0.74, 0.48, 0.24, 0.58, 0.35, 0.16)
                bar_width, gap = 3.0, 3.0
                total_width = len(levels) * bar_width + (len(levels) - 1) * gap
                x0 = (bars_width - total_width) / 2.0
                center_y = bars_height / 2.0
                for index, level in enumerate(levels):
                    height = 3.0 + level * (bars_height - 5.0)
                    painter.setBrush(QColor(82, 91, 102, 190))
                    painter.drawRoundedRect(
                        QRectF(x0 + index * (bar_width + gap), center_y - height / 2.0,
                               bar_width, height),
                        bar_width / 2.0, bar_width / 2.0,
                    )
                painter.end()
                bars_path = os.path.join(
                    tempfile.gettempdir(), f"assistant_chat_audio_bars_{os.getpid()}.png"
                )
                pix.save(bars_path, "PNG")
                question = f'<img src="{Path(bars_path).as_uri()}" width="78" height="28" />'
            else:
                question = html.escape(raw_question).replace("\n", "<br>")
            user_row = QWidget(dialog.conversation_widget)
            dialog._turn_rows.append(user_row)
            user_row.setStyleSheet(qss_transparent_surface())
            user_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            user_row.setMaximumWidth(available)
            user_layout = QHBoxLayout(user_row)
            user_layout.setContentsMargins(8, 0, 8, 0)
            user_layout.setSpacing(0)
            user_bubble = ChatBubble("user", user_row, dialog.FONT_SIZE_OFFSET)
            user_bubble.set_skill_tag(turn.get("skill_tag"))
            user_bubble.set_timestamp(turn.get("timestamp", ""))
            # Les pièces jointes sont affichées avant la question, comme dans le
            # compositeur, puis la bulle épouse le contenu et reste alignée à droite.
            user_bubble.set_html(turn.get("attachments_html", "") + question)
            user_bubble.setMaximumWidth(user_bubble_width)
            user_bubble.fit_to_content_width(user_bubble_width, minimum_width=0)
            user_layout.addStretch(1)
            user_layout.addWidget(user_bubble, 0, Qt.AlignRight | Qt.AlignTop)
            dialog.conversation_layout.addWidget(user_row)

            answer = dialog._answer_without_sources(turn.get("answer", ""))
            error_message = turn.get("error", "")
            tools = turn.get("tools", [])
            is_loading = turn.get("loading", False)

            if tools or answer or error_message or is_loading or turn.get("thinking") or turn.get("timeline"):
                assistant_row = QWidget(dialog.conversation_widget)
                assistant_row.setStyleSheet(qss_transparent_surface())
                assistant_row.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Minimum
                )
                assistant_layout = QVBoxLayout(assistant_row)
                # La largeur de la bulle inclut déjà l'espace disponible du viewport.
                # Une marge droite supplémentaire agrandit le widget interne au-delà
                # du viewport et décale toute la conversation vers la gauche.
                assistant_layout.setContentsMargins(
                    0, 0, 0, 10 if error_message else 0
                )
                assistant_layout.setSpacing(6)
                assistant_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

                timeline = turn.get("timeline") or []
                if timeline:
                    last_response_index = max(
                        (
                            index
                            for index, item in enumerate(timeline)
                            if item.get("type") == "response"
                        ),
                        default=-1,
                    )
                    for index, event in enumerate(timeline):
                        event_type = event.get("type")
                        if event_type == "thinking":
                            thinking_widget = ThinkingGroupWidget(assistant_row, font_size_offset=dialog.FONT_SIZE_OFFSET)
                            thinking_widget.setFixedWidth(bubble_width)
                            thinking_widget.append_text(event.get("text", ""))
                            is_current_stream = (
                                turn_index == dialog.current_turn_index
                                and index == len(timeline) - 1
                                and turn.get("loading", False)
                            )
                            if not is_current_stream:
                                duration = turn.get("thinking_duration")
                                if duration is not None:
                                    thinking_widget.finish(duration)
                                else:
                                    thinking_widget.collapse()
                            else:
                                thinking_widget.title.start_animation()
                            thinking_widget.toggled.connect(
                                dialog._on_tool_widget_toggled
                            )
                            if is_current_stream:
                                dialog.current_thinking_widget = thinking_widget
                            assistant_layout.addWidget(thinking_widget, 0, Qt.AlignLeft)
                        elif event_type == "response":
                            response_text = dialog._answer_without_sources(
                                event.get("text", "")
                            )
                            if not response_text:
                                continue
                            rendered = (
                                dialog.host.markdown_to_html(
                                    response_text, dialog.FONT_SIZE_OFFSET
                                )
                                if dialog.host is not None
                                else html.escape(response_text).replace("\n", "<br>")
                            )
                            assistant_bubble = ChatBubble(
                                "assistant", assistant_row, dialog.FONT_SIZE_OFFSET
                            )
                            assistant_bubble.setFixedWidth(bubble_width)
                            assistant_bubble.link_clicked.connect(
                                dialog._open_source_link
                            )
                            sources = (
                                turn.get("sources_html", "")
                                if index == last_response_index
                                else ""
                            )
                            assistant_bubble.set_html(rendered + sources)
                            if (
                                turn_index == dialog.current_turn_index
                                and event is timeline[-1]
                            ):
                                dialog.current_assistant_bubble = assistant_bubble
                            assistant_layout.addWidget(
                                assistant_bubble, 0, Qt.AlignLeft
                            )
                        elif event_type == "tools":
                            tool_widget = ToolExecutionGroupWidget(
                                event.get("tools", []),
                                turn=turn,
                                parent=assistant_row,
                            )
                            tool_widget.setFixedWidth(bubble_width)
                            tool_widget.toggled.connect(dialog._on_tool_widget_toggled)
                            assistant_layout.addWidget(tool_widget, 0, Qt.AlignLeft)

                    if error_message:
                        error_bubble = ChatBubble(
                            "error", assistant_row, dialog.FONT_SIZE_OFFSET
                        )
                        error_bubble.setFixedWidth(bubble_width)
                        error_bubble.set_html(
                            f"<b>Erreur d'exécution</b><br>"
                            f"{html.escape(error_message).replace(chr(10), '<br>')}"
                        )
                        assistant_layout.addWidget(error_bubble, 0, Qt.AlignLeft)
                    dialog.conversation_layout.addWidget(assistant_row)
                    continue

                thinking = turn.get("thinking", "")
                answer_before_tools = bool(
                    answer
                    and tools
                    and turn.get("response_start_time")
                    and turn.get("tool_start_time")
                    and turn["response_start_time"] < turn["tool_start_time"]
                )
                thinking_after_tools = bool(
                    thinking
                    and tools
                    and turn.get("thinking_start_time")
                    and turn.get("tool_end_time")
                    and turn["thinking_start_time"] >= turn["tool_end_time"]
                )

                def add_thinking_widget():
                    nonlocal thinking
                    if not thinking:
                        return
                    thinking_widget = ThinkingGroupWidget(assistant_row, font_size_offset=dialog.FONT_SIZE_OFFSET)
                    thinking_widget.setFixedWidth(bubble_width)
                    thinking_widget.append_text(thinking)
                    if answer:
                        duration = turn.get("thinking_duration")
                        if duration is not None:
                            thinking_widget.finish(duration)
                        else:
                            thinking_widget.collapse()
                    elif turn_index == dialog.current_turn_index and turn.get("loading", False):
                        thinking_widget.title.start_animation()
                    thinking_widget.toggled.connect(
                        dialog._on_tool_widget_toggled
                    )
                    if turn_index == dialog.current_turn_index:
                        dialog.current_thinking_widget = thinking_widget
                    assistant_layout.addWidget(thinking_widget, 0, Qt.AlignLeft)

                def add_answer_widget():
                    if not answer:
                        return
                    rendered = (
                        dialog.host.markdown_to_html(answer, dialog.FONT_SIZE_OFFSET)
                        if dialog.host is not None
                        else html.escape(answer).replace("\n", "<br>")
                    )
                    assistant_bubble = ChatBubble(
                        "assistant", assistant_row, dialog.FONT_SIZE_OFFSET
                    )
                    assistant_bubble.setFixedWidth(bubble_width)
                    assistant_bubble.link_clicked.connect(dialog._open_source_link)
                    assistant_bubble.set_html(
                        rendered + turn.get("sources_html", "")
                    )
                    if turn_index == dialog.current_turn_index:
                        dialog.current_assistant_bubble = assistant_bubble
                    assistant_layout.addWidget(assistant_bubble, 0, Qt.AlignLeft)

                if not thinking_after_tools:
                    add_thinking_widget()
                if answer_before_tools:
                    add_answer_widget()

                # A. Une seule timeline groupée pour toutes les étapes du tour.
                if tools:
                    tool_widget = ToolExecutionGroupWidget(
                        tools, turn=turn, parent=assistant_row
                    )
                    tool_widget.setFixedWidth(bubble_width)
                    tool_widget.toggled.connect(dialog._on_tool_widget_toggled)
                    assistant_layout.addWidget(tool_widget, 0, Qt.AlignLeft)

                if thinking_after_tools:
                    add_thinking_widget()

                # B. Indicateur de génération bleu, visible pendant toute la
                # préparation de la réponse, y compris pendant un appel outil.
                if is_loading and not answer and not thinking:
                    dots_row = QWidget(assistant_row)
                    dots_row.setStyleSheet(qss_transparent_surface())
                    dots_layout = QHBoxLayout(dots_row)
                    dots_layout.setContentsMargins(0, 0, 0, 0)
                    dots_layout.setSpacing(7)
                    status_label = ShimmerLabel(
                        turn.get("thinking_status", "Analyse de la demande"),
                        dots_row,
                    )
                    status_label.start_animation()
                    status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    status_label.setStyleSheet(
                        f"font-family:{t.FONT_TEXT}; font-size:{int(t.SIZE_SM.rstrip('px')) + dialog.FONT_SIZE_OFFSET}px; "
                        "background:transparent;"
                    )
                    dots_layout.addWidget(status_label, 0, Qt.AlignLeft | Qt.AlignTop)
                    dots_layout.addStretch(1)
                    assistant_layout.addWidget(dots_row, 0, Qt.AlignLeft)

                # C. Bulle de réponse du LLM
                if not answer_before_tools:
                    add_answer_widget()

                if error_message:
                    error_bubble = ChatBubble("error", assistant_row, dialog.FONT_SIZE_OFFSET)
                    error_bubble.setFixedWidth(bubble_width)
                    error_bubble.set_html(
                        f"<b>Erreur d'exécution</b><br>{html.escape(error_message).replace(chr(10), '<br>')}"
                    )
                    assistant_layout.addWidget(error_bubble, 0, Qt.AlignLeft)

                dialog.conversation_layout.addWidget(assistant_row)
        dialog.response.show()
        dialog._sync_conversation_widget_height()
        dialog._update_height()
        dialog.conversation_widget.adjustSize()
        QTimer.singleShot(0, dialog._refresh_stream_view)
        QTimer.singleShot(0, dialog._update_turn_navigation_visibility)

    def _update_turn_navigation_visibility(self):
        dialog = self.dialog
        return dialog.conversation_controller.update_navigation_visibility()

    def _refresh_conversation_widths(self):
        dialog = self.dialog
        """Réapplique les largeurs après stabilisation de la géométrie du viewport."""
        if not dialog.turns or not dialog.response.isVisible():
            return
        viewport_width = dialog.response.viewport().width()
        if viewport_width <= 150:
            viewport_width = dialog.width() - 32
        # La largeur retournée par viewport() est déjà amputée de la scrollbar.
        available = max(160, viewport_width)
        bubble_width = max(120, available - 16)
        for widget_type in (
            ThinkingGroupWidget,
            ToolExecutionGroupWidget,
        ):
            for widget in dialog.conversation_widget.findChildren(widget_type):
                widget.setFixedWidth(bubble_width)
        for bubble in dialog.conversation_widget.findChildren(ChatBubble):
            if bubble.role != "user":
                bubble.setFixedWidth(bubble_width)
        dialog._sync_conversation_widget_height()
        dialog._update_response_scroll_policy()

    def _scroll_to_bottom(self):
        dialog = self.dialog
        bar = dialog.response.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _sync_conversation_widget_height(self):
        dialog = self.dialog
        """Aligne la hauteur interne sur le contenu courant, sans hauteur résiduelle."""
        dialog.conversation_widget.setMinimumHeight(0)
        dialog.conversation_widget.setMaximumHeight(16777215)
        for bubble in dialog.conversation_widget.findChildren(ChatBubble):
            bubble._fit_height()
        for i in range(dialog.conversation_layout.count()):
            item = dialog.conversation_layout.itemAt(i)
            w = item.widget() if item else None
            if w and w.layout():
                w.layout().invalidate()
                w.layout().activate()
                w.updateGeometry()
        dialog.conversation_layout.invalidate()
        dialog.conversation_layout.activate()
        content_height = max(1, dialog.conversation_layout.sizeHint().height())
        dialog.conversation_widget.setFixedHeight(content_height)
        dialog.conversation_widget.updateGeometry()

    def _update_response_scroll_policy(self):
        dialog = self.dialog
        """Affiche la scrollbar uniquement si le contenu dépasse réellement le viewport."""
        dialog.response.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dialog.response.widget().adjustSize()
        viewport_height = dialog.response.viewport().height()
        content_height = dialog.conversation_widget.height()
        if content_height > viewport_height + 1:
            dialog.response.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            dialog.response.verticalScrollBar().setValue(0)

    def _refresh_stream_view(self):
        dialog = self.dialog
        """Recalcule le document avant de positionner le scrollbar de streaming."""
        scroll_bar = dialog.response.verticalScrollBar()
        follow_bottom = scroll_bar.value() >= scroll_bar.maximum() - 2
        previous_value = scroll_bar.value()
        dialog._sync_conversation_widget_height()
        dialog.response.widget().adjustSize()
        dialog.response.updateGeometry()
        dialog._update_height()
        dialog._sync_conversation_widget_height()
        dialog.response.widget().adjustSize()
        dialog._update_response_scroll_policy()
        dialog._update_turn_navigation_visibility()
        if follow_bottom:
            dialog._scroll_to_bottom()
        else:
            scroll_bar.setValue(min(previous_value, scroll_bar.maximum()))

    def _update_height(self):
        dialog = self.dialog
        dialog.layout().activate()
        dialog.composer.layout().activate()
        dialog.content_widget.layout().activate()

        response_h = 0
        if dialog.response.isVisible():
            dialog._sync_conversation_widget_height()
            dialog.conversation_layout.activate()
            doc_h = dialog.conversation_layout.sizeHint().height() + 4
            if dialog.streaming_response_active:
                # Une hauteur stable évite la recomposition répétée de la fenêtre
                # translucide/Acrylic pendant l'arrivée des tokens.
                response_h = dialog.MAX_RESPONSE_HEIGHT
            else:
                response_h = max(45, min(dialog.MAX_RESPONSE_HEIGHT, doc_h))
            dialog.response.setFixedHeight(response_h)
            dialog._update_response_scroll_policy()
        else:
            dialog.response.setFixedHeight(0)
        if hasattr(self, "turn_navigation"):
            QTimer.singleShot(0, dialog._update_turn_navigation_visibility)

        # The response and composer are stacked vertically. Computing the height
        # explicitly avoids the conversation being painted behind the composer.
        header_h = 36
        separator_h = 1 if dialog.separator_container.isVisible() else 0
        top_bottom_margins = 16
        content_spacing = 4 if response_h else 0
        composer_h = max(38, dialog.composer.sizeHint().height())
        target = header_h + separator_h + top_bottom_margins + content_spacing + response_h + composer_h + 2

        # Quand l'utilisateur tape '/' au début de la conversation (ou quand la fenêtre
        # est encore petite), on agrandit la hauteur pour afficher entièrement le menu
        # des commandes skills sans être coupé, tant que l'on ne dépasse pas MAX_HEIGHT.
        if hasattr(self, 'slash_popup') and dialog.slash_popup.isVisible():
            popup_h = dialog.slash_popup.content_height() if hasattr(dialog.slash_popup, 'content_height') else dialog.slash_popup.height()
            min_needed_for_slash = header_h + separator_h + top_bottom_margins + composer_h + popup_h + 12
            target = max(target, min_needed_for_slash)

        # Une fois que la fenêtre Ctrl+9 a augmenté en hauteur, ne rediminuer la hauteur
        # que si explicitement autorisé (fin de streaming, repli d'étape, etc.).
        if getattr(self, "_allow_shrink_height", False):
            dialog._allow_shrink_height = False
            dialog.expanded_height = target
        elif not dialog.is_collapsed:
            target = max(dialog.height(), target, dialog.expanded_height)

        target = max(dialog.MIN_HEIGHT, min(dialog.MAX_HEIGHT, target))

        if not dialog.is_collapsed and abs(dialog.height() - target) > 2:
            dialog.setFixedHeight(target)
            dialog.expanded_height = target

        # Repositionner le popup slash flottant au-dessus du compositeur
        if hasattr(self, 'slash_popup') and dialog.slash_popup.isVisible():
            dialog._position_slash_popup()

    def _add_sources_html(self, answer, documents):
        return self.source_renderer.render(answer, documents)
