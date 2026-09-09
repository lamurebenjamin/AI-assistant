"""Gestionnaires de raccourcis clavier globaux (voix, menu contextuel, raccourcis numériques)."""

import keyboard
from PyQt5.QtCore import QTimer

from src.config.schema import LOGGER
from src.platform.foreground import is_adobe_reader_foreground


class VoiceHotkeyManager:
    """Gère séparément l'appui et le relâchement de Ctrl+Alt+1 à Ctrl+Alt+9."""
    def __init__(self, assistant):
        self.assistant = assistant
        self.pressed = set()
        self.active_index = None
        self.enabled = True
        self.hook = keyboard.hook(self._event, suppress=False)

    def _event(self, event):
        name = (event.name or "").lower()
        if name == "esc" and event.event_type == "down" and (self.active_index is not None or self.assistant.voice_sending):
            self.assistant.voice_cancel_signal.emit(); return
        tracked = {"ctrl", "left ctrl", "right ctrl", "alt", "left alt", "right alt"} | {str(i) for i in range(1, 10)}
        if name not in tracked: return
        if event.event_type == "down": self.pressed.add(name)
        else: self.pressed.discard(name)
        ctrl_down = bool(self.pressed.intersection({"ctrl", "left ctrl", "right ctrl"}))
        alt_down = bool(self.pressed.intersection({"alt", "left alt", "right alt"}))
        digit = next((i for i in range(1, 10) if str(i) in self.pressed), None)
        if self.enabled and ctrl_down and alt_down and digit is not None and self.active_index is None:
            self.active_index = digit - 1
            self.assistant.voice_press_signal.emit(self.active_index)
        elif self.active_index is not None and (not ctrl_down or not alt_down or str(self.active_index + 1) not in self.pressed):
            released_index = self.active_index
            self.active_index = None
            self.assistant.voice_release_signal.emit(released_index)

    def set_enabled(self, enabled): self.enabled = bool(enabled)
    def stop(self):
        if self.hook is not None: keyboard.unhook(self.hook); self.hook = None

# ==========================================
# THREAD LLAMA.CPP
# ==========================================
from src.llm.client import LlamaThread

# ==========================================
# ANALYSE LOCALE DE DOCUMENTS — PDF / IMAGES
# ==========================================
from src.documents.pdf_utils import (
    normalize_page_selection as _normalize_page_selection,
    extract_pdf_context as _extract_pdf_context,
    open_pdf_at_page as _open_pdf_at_page,
)
from src.documents.payload_builder import (
    document_image_data_url as _document_image_data_url,
    prepare_document_payload as _prepare_document_payload,
)
from src.documents.thread import DocumentAnalysisThread


from src.ui.widgets.chat_bubble import SourceZoomTextBrowser, ChatBubble
from src.ui.widgets.animated_buttons import AnimatedComposerButton
from src.ui.widgets.attachment_widget import AttachmentPreviewWidget
from src.ui.widgets.message_editor import MessageTextEdit
from src.ui.widgets.thinking_dots import ThinkingDots

from src.ui.windows.document_dialog import DocumentDialog


class MenuHotkeyManager:
    """Gère proprement l'enregistrement de Ctrl+. sans toucher aux autres hooks."""

    def __init__(self, assistant):
        self.assistant = assistant
        self.handle = None
        self.enabled = False
        self.set_enabled(True)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self.handle = keyboard.add_hotkey(
                "ctrl+.", self.assistant.show_menu_signal.emit, suppress=False
            )
        elif self.handle is not None:
            # Le raccourci peut avoir deja ete retire par un nettoyage global.
            # Dans ce cas, keyboard.remove_hotkey leve ValueError/KeyError.
            try:
                keyboard.remove_hotkey(self.handle)
            except (KeyError, ValueError):
                pass
            finally:
                self.handle = None

    def stop(self):
        self.set_enabled(False)


class NumericHotkeyManager:
    """Gère Ctrl+0 à Ctrl+9 en neutralisant le zoom d'Adobe Reader/Acrobat.

    Par défaut, ces combinaisons sont transmises normalement au système
    (suppress=False) afin de ne pas gêner les autres applications. Dès que
    Adobe Reader ou Acrobat passe au premier plan, les raccourcis sont
    ré-enregistrés avec suppress=True : ils déclenchent uniquement les
    actions de l'assistant et n'atteignent plus Adobe, qui ne peut donc
    plus interpréter Ctrl+0..9 comme des raccourcis de zoom.
    """

    POLL_INTERVAL_MS = 250

    def __init__(self, assistant, parent=None):
        self.assistant = assistant
        self.enabled = True
        self.suppressed = None  # Force un premier enregistrement.
        self.timer = QTimer(parent)
        self.timer.setInterval(self.POLL_INTERVAL_MS)
        self.timer.timeout.connect(self._poll_foreground_app)
        self._register(suppress=False)
        self.timer.start()

    def _make_callback(self, index):
        if index < 0:
            # Ctrl+0 replie ou déplie la fenêtre visible, comme un clic sur sa barre de titre.
            return self.assistant.toggle_collapse_signal.emit
        return lambda: self.assistant.trigger_direct_signal.emit(index)

    def _register(self, suppress):
        self._unregister()
        self.suppressed = suppress
        for i in range(0, 10):
            # Ctrl+9 est réservé à l'analyse documentaire : il est toujours
            # supprimé du logiciel au premier plan pour éviter, par exemple,
            # le raccourci Ctrl+9 d'un navigateur ou d'un autre logiciel.
            effective_suppress = True if i == 9 else suppress
            keyboard.add_hotkey(
                f'ctrl+{i}',
                self._make_callback(i - 1),
                suppress=effective_suppress
            )

    def _unregister(self):
        for i in range(0, 10):
            try:
                keyboard.remove_hotkey(f'ctrl+{i}')
            except (KeyError, ValueError):
                pass

    def _poll_foreground_app(self):
        if not self.enabled:
            return
        should_suppress = is_adobe_reader_foreground()
        if should_suppress != self.suppressed:
            self._register(suppress=should_suppress)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if enabled:
            self.suppressed = None
            self._register(suppress=is_adobe_reader_foreground())
            self.timer.start()
        else:
            self.timer.stop()
            self._unregister()
            self.suppressed = None

    def stop(self):
        self.timer.stop()
        self._unregister()
