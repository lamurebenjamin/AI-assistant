"""Éditeur de texte riche pour la composition de requêtes avec support du glisser-déposer/coller d'images."""

import os
import tempfile
import time
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTextEdit


class MessageTextEdit(QTextEdit):
    """Champ de saisie : Entrée envoie, Maj+Entrée insère une nouvelle ligne."""

    send_requested = pyqtSignal()
    pasted_files = pyqtSignal(list)

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

    def wheelEvent(self, event):
        self.verticalScrollBar().setValue(0)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                # Maj+Entrée insère toujours un saut de ligne, y compris avec
                # la touche Entrée du pavé numérique.
                super().keyPressEvent(event)
            elif not (
                modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
            ):
                # Entrée envoie. Qt ajoute parfois KeypadModifier pour l'Entrée
                # du pavé numérique, qui doit se comporter comme Entrée classique.
                self.send_requested.emit()
                event.accept()
            else:
                super().keyPressEvent(event)
            return
        super().keyPressEvent(event)
