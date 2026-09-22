import os
import re
import tempfile
import time
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit


class MessageTextEdit(QTextEdit):
    """Champ de saisie : Entrée envoie, Maj+Entrée insère une nouvelle ligne, '/' ouvre les actions."""

    send_requested = Signal()
    pasted_files = Signal(list)
    slash_triggered = Signal(str, int)
    slash_dismissed = Signal()
    skill_tag_removed = Signal()
    history_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slash_popup = None
        self.skill_tag_range = None
        self.textChanged.connect(self._check_slash_command)

    def set_skill_tag_range(self, start: int, end: int) -> None:
        self.skill_tag_range = (start, end)

    def remove_skill_tag(self) -> bool:
        if not self.skill_tag_range:
            return False
        start, end = self.skill_tag_range
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
        self.skill_tag_range = None
        self.skill_tag_removed.emit()
        return True

    def set_slash_popup(self, popup):
        self.slash_popup = popup

    def insertFromMimeData(self, source):
        if source is not None and source.hasImage():
            image = source.imageData()
            if image is not None and not image.isNull():
                path = os.path.join(
                    tempfile.gettempdir(),
                    f"assistant_clipboard_{os.getpid()}_{time.monotonic_ns()}.png",
                )
                if image.save(path, "PNG"):
                    self.pasted_files.emit([path])
                    return
        if source is not None and source.hasUrls():
            paths = [u.toLocalFile() for u in source.urls() if u.isLocalFile()]
            if paths:
                self.pasted_files.emit(paths)
                return
        super().insertFromMimeData(source)
        self._check_slash_command()

    def wheelEvent(self, event):
        self.verticalScrollBar().setValue(0)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete) and self.skill_tag_range:
            start, end = self.skill_tag_range
            position = self.textCursor().position()
            if (
                (event.key() == Qt.Key_Backspace and start < position <= end + 1)
                or (event.key() == Qt.Key_Delete and start <= position < end)
            ):
                self.remove_skill_tag()
                event.accept()
                self._check_slash_command()
                return
        # 1. Si le menu slash command est affiché, intercepter la navigation et la validation
        if self.slash_popup is not None and self.slash_popup.isVisible():
            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                if self.slash_popup.navigate(event.key()):
                    event.accept()
                    return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                if self.slash_popup.select_current():
                    event.accept()
                    return
            elif event.key() == Qt.Key_Escape:
                self.slash_popup.hide()
                self.slash_dismissed.emit()
                event.accept()
                return

        # L'historique est réservé au champ vide. Avec du texte présent,
        # les flèches restent la navigation normale du QTextEdit.
        if (
            event.key() in (Qt.Key_Up, Qt.Key_Down)
            and not self.toPlainText().strip()
            and not (
                event.modifiers()
                & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier | Qt.ShiftModifier)
            )
        ):
            self.history_requested.emit(
                -1 if event.key() == Qt.Key_Up else 1
            )
            event.accept()
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                super().keyPressEvent(event)
            elif not (
                modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
            ):
                self.send_requested.emit()
                event.accept()
            else:
                super().keyPressEvent(event)
            self._check_slash_command()
            return

        super().keyPressEvent(event)
        self._check_slash_command()

    def _check_slash_command(self):
        cursor = self.textCursor()
        pos = cursor.position()
        full_text = self.toPlainText()
        text_before_cursor = full_text[:pos]

        match = re.search(r'(?:^|\s)/([^\s]*)$', text_before_cursor)
        if match:
            query = match.group(1)
            slash_pos = match.start() if text_before_cursor[match.start()] == '/' else match.start() + 1
            self.slash_triggered.emit(query, slash_pos)
        else:
            self.slash_dismissed.emit()
