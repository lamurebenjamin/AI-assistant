"""Compositeur de message partagé (champ, micro, envoi, pièces jointes)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel

import src.ui.design_tokens as t
from src.ui.fluent_compat import install_tooltip
from src.ui.widgets.animated_buttons import AnimatedComposerButton
from src.ui.widgets.audio_bars import ScrollingAudioBars
from src.ui.widgets.message_editor import MessageTextEdit
from src.ui.widgets.skill_tag import SkillTag


class ComposerBar(QFrame):
    """Barre de saisie Ctrl+9 : pièces jointes, texte, micro et envoi."""

    def __init__(self, parent=None, *, font_size_offset: int = 0, document_area=None):
        super().__init__(parent)
        self.font_size_offset = font_size_offset
        self.setObjectName("Composer")
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(2)
        if document_area is not None:
            outer.addWidget(document_area)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.add_button = AnimatedComposerButton("add")
        install_tooltip(self.add_button, "Ajouter un document ou lancer une skill")

        self.skill_tag = SkillTag(
            self, font_size_offset=font_size_offset, framed=True
        )

        self.question = MessageTextEdit()
        self.question.setPlaceholderText("Message assistant IA")
        self.question.setFocusPolicy(Qt.StrongFocus)
        self.question.setFixedHeight(t.COMPOSER_HEIGHT)
        self.question.setContentsMargins(0, 0, 0, 0)
        self.question.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.question.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.question.document().setDocumentMargin(0)
        self.question.setViewportMargins(0, 0, 0, 0)
        self.question.setAcceptDrops(False)
        self.question.viewport().setAcceptDrops(False)
        self.question.verticalScrollBar().setValue(0)

        self.audio_bars = ScrollingAudioBars(self)
        self.audio_bars.setFocusPolicy(Qt.NoFocus)
        self.skill_tag.setFocusPolicy(Qt.NoFocus)
        self.mic = AnimatedComposerButton("mic")
        install_tooltip(self.mic, "Dicter")
        self.send = AnimatedComposerButton("send")
        install_tooltip(self.send, "Envoyer")
        self.send.hide()
        self.stop_generation_button = AnimatedComposerButton("stop")
        install_tooltip(self.stop_generation_button, "Arrêter la génération")
        self.stop_generation_button.hide()

        row.addWidget(self.add_button, 0, Qt.AlignVCenter)
        row.addWidget(self.question, 1, Qt.AlignVCenter)
        row.addWidget(self.audio_bars, 1, Qt.AlignVCenter)
        row.addWidget(self.mic, 0, Qt.AlignVCenter)
        row.addWidget(self.send, 0, Qt.AlignVCenter)
        row.addWidget(self.stop_generation_button, 0, Qt.AlignVCenter)
        outer.addLayout(row)
        # Reparent all controls through the layout before defining tab order.
        # Calling setTabOrder while the row is detached makes Qt see different
        # top-level windows and emits a warning.
        QWidget.setTabOrder(self.add_button, self.question)
        QWidget.setTabOrder(self.question, self.mic)
        QWidget.setTabOrder(self.mic, self.send)
        QWidget.setTabOrder(self.send, self.stop_generation_button)

        self.drop_feedback = BodyLabel("Déposer pour ajouter le document", self)
        self.drop_feedback.setAlignment(Qt.AlignCenter)
        self.drop_feedback.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.drop_feedback.setFocusPolicy(Qt.NoFocus)
        self.drop_feedback.hide()
        self.refresh_theme()

    def refresh_theme(self) -> None:
        offset = self.font_size_offset
        size_md = int(t.SIZE_MD.rstrip("px")) + offset
        self.question.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;"
            f"padding:{t.COMPOSER_TEXT_PADDING}px 1px;color:{t.COLOR_TEXT_PRIMARY};"
            f"font-family:{t.FONT_TEXT};font-size:{size_md}px;}}"
        )
        self.drop_feedback.setStyleSheet(
            f"QLabel{{background:{t.COLOR_PRIMARY_LIGHT};color:{t.COLOR_PRIMARY};"
            f"border:2px solid {t.COLOR_PRIMARY};border-radius:{t.RADIUS_LG};"
            f"font-family:{t.FONT_TEXT};font-size:{size_md}px;font-weight:700;}}"
        )
        self.skill_tag.refresh_theme()
