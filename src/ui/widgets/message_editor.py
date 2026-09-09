import os
import re
import tempfile
import time
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTextEdit


class MessageTextEdit(QTextEdit):
    """Champ de saisie : Entrée envoie, Maj+Entrée insère une nouvelle ligne, '/' ouvre les actions."""

    send_requested = pyqtSignal()
    pasted_files = pyqtSignal(list)
    slash_triggered = pyqtSignal(str, int)
    slash_dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slash_popup = None
        self.textChanged.connect(self._check_slash_command)

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
