"""Selection, presse-papiers et ouverture explicite des liens."""

import os
import sys
import time

import keyboard
import pyperclip
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices

from src.config.schema import LOGGER


def get_selected_text(self):
    """Copie de façon fiable le texte sélectionné, y compris dans les lecteurs PDF."""
    try:
        clipboard_backup = pyperclip.paste()
    except Exception:  # noqa: BLE001
        clipboard_backup = ""

    marker = f"__ASSISTANT_COPY_{time.monotonic_ns()}__"

    def read_new_clipboard(timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.04)
            try:
                value = pyperclip.paste()
            except Exception:  # noqa: BLE001
                LOGGER.debug("Lecture du presse-papiers indisponible", exc_info=True)
                continue
            if value != marker:
                return str(value).rstrip("\r\n")
        return ""

    try:
        # Le raccourci global contient Ctrl. Certains lecteurs PDF, notamment
        # Acrobat, ignorent Ctrl+C si la touche du raccourci est encore enfoncée.
        deadline = time.monotonic() + 1.0
        while keyboard.is_pressed('ctrl') and time.monotonic() < deadline:
            time.sleep(0.02)

        # Libère les modificateurs susceptibles d'être restés actifs, puis
        # laisse au lecteur PDF le temps de récupérer son focus clavier.
        for key in ('ctrl', 'shift', 'alt'):
            try:
                keyboard.release(key)
            except Exception:  # noqa: BLE001,S110
                pass
        time.sleep(0.12)

        # Plusieurs tentatives avec délais réduits pour éviter de bloquer l'interface
        # lorsque rien n'est sélectionné.
        for shortcut, timeout in (('ctrl+c', 0.25), ('ctrl+c', 0.35), ('ctrl+insert', 0.35)):
            pyperclip.copy(marker)
            time.sleep(0.04)
            keyboard.send(shortcut)
            copied = read_new_clipboard(timeout)
            if copied:
                return copied
            time.sleep(0.06)
        return ""
    finally:
        try:
            pyperclip.copy(clipboard_backup)
        except Exception:  # noqa: BLE001,S110
            pass


def copy_response(self):
    _, answer_text = self.split_thinking_and_answer(self.response_text)
    if self.current_request_is_audio:
        _, answer_text = self.parse_audio_response(answer_text)
    if answer_text:
        try:
            pyperclip.copy(answer_text)
        except pyperclip.PyperclipException:
            self.copy_button.setToolTip("Presse-papiers indisponible")
            return
        self.animate_copy_button()
        self.copy_button.setToolTip("Réponse copiée")
        QTimer.singleShot(1500, lambda: self.copy_button.setToolTip("Copier la réponse"))


def open_response_link(self, href):
    """Ouvre explicitement les fichiers locaux avec l'application Windows associée."""
    try:
        url = QUrl(str(href))
        if url.scheme().lower() == "file":
            local_path = url.toLocalFile()
            if local_path and os.path.isfile(local_path):
                if sys.platform == "win32":
                    os.startfile(local_path)
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(local_path))
                return
            LOGGER.warning("Fichier lié introuvable : %s", local_path)
            return
        QDesktopServices.openUrl(url)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Impossible d'ouvrir le lien : %s", href)
