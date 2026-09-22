"""Conversation rendering, source links, and turn navigation for DocumentDialog."""

import base64
import json
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices


class ConversationController:
    """Coordinates conversation-specific UI while keeping the dialog API stable."""

    def __init__(self, dialog):
        self.dialog = dialog

    def render(self):
        return self.dialog._render_conversation_impl()

    def navigate_to_turn(self, turn_index):
        dialog = self.dialog
        if turn_index < 0 or turn_index >= len(dialog.turns):
            return
        dialog.conversation_layout.activate()
        target = (
            dialog._turn_rows[turn_index]
            if turn_index < len(dialog._turn_rows)
            else None
        )
        if target is None:
            return
        scrollbar = dialog.response.verticalScrollBar()
        scrollbar.setValue(max(0, target.y()))
        for index, button in enumerate(dialog._turn_navigation_buttons):
            button.setChecked(index == turn_index)
            size = 14 if index == turn_index else 8
            button.setFixedSize(size, size)

    def update_navigation_visibility(self):
        dialog = self.dialog
        visible = dialog.response.isVisible() and bool(dialog.turns)
        dialog.turn_navigation.setVisible(visible)
        if visible:
            dialog.turn_navigation_layout.setAlignment(
                Qt.AlignVCenter | Qt.AlignHCenter
            )
            dialog.turn_navigation.setFixedHeight(
                max(24, dialog.turn_navigation_layout.sizeHint().height() + 8)
            )

    def open_source_link(self, url):
        dialog = self.dialog
        value = url.toString()
        if url.scheme().lower() == "file":
            if dialog.host is not None:
                dialog.host.open_response_link(value)
            else:
                QDesktopServices.openUrl(url)
            return
        image_match = re.match(r"^sourceimage:([A-Za-z0-9_-]+)$", value)
        if image_match:
            try:
                token = image_match.group(1)
                padding = "=" * (-len(token) % 4)
                payload = base64.urlsafe_b64decode(
                    (token + padding).encode("ascii")
                ).decode("utf-8")
                metadata = json.loads(payload)
                dialog._show_source_image_large(
                    metadata.get("path", ""),
                    metadata.get("title", "Source surlignée"),
                )
            except (ValueError, UnicodeDecodeError):
                pass
            return
        if dialog.host is None:
            return
        match = re.match(r"^source:(\d+):([A-Za-z0-9_-]+)$", value)
        if not match:
            return
        try:
            token = match.group(2)
            padding = "=" * (-len(token) % 4)
            filename = base64.urlsafe_b64decode(
                (token + padding).encode("ascii")
            ).decode("utf-8")
            dialog.host.open_document_source(filename, int(match.group(1)))
        except (ValueError, UnicodeDecodeError):
            return

    def show_source_captures(self, answer, documents):
        dialog = self.dialog
        if not dialog.turns:
            return
        sources = dialog._add_sources_html(answer, documents)
        if sources:
            dialog.turns[-1]["sources_html"] = sources
            self.render()
