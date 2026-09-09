"""Fenêtre d'analyse et de dialogue documentaire (PDF, images, texte)."""

import base64
import html
import json
import os
import re
import tempfile
import time
from pathlib import Path

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from src.config.schema import APP_DIR, LOGGER
from src.ui.design_tokens import (
    COLOR_BG_ACRYLIC,
    COLOR_BG_PAGE,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_ACRYLIC,
    COLOR_BORDER_INPUT,
    COLOR_BORDER_SUBTLE,
    COLOR_DANGER,
    COLOR_GRAY_200,
    COLOR_GRAY_500,
    COLOR_GRAY_700,
    COLOR_HOVER_DARK,
    COLOR_PRESS_DARK,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_LIGHT,
    COLOR_SCROLLBAR_HOVER,
    COLOR_SCROLLBAR_THUMB,
    COLOR_SCROLLBAR_TRACK,
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_DISPLAY,
    FONT_TEXT,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_LG,
    RADIUS_XL,
    RADIUS_2XL,
    SIZE_XS,
    SIZE_SM,
    SIZE_MD,
    SIZE_LG,
)
from src.ui.icons import ICONS_DARK, create_svg_icon, get_logo_pixmap
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedComposerButton, AnimatedHeaderButton
from src.ui.widgets.attachment_widget import AttachmentPreviewWidget
from src.ui.widgets.audio_bars import ScrollingAudioBars
from src.ui.widgets.chat_bubble import ChatBubble
from src.ui.widgets.message_editor import MessageTextEdit
from src.ui.widgets.thinking_dots import ThinkingDots
from src.audio.recorder import AudioRecorderThread
class DocumentDialog(QDialog):
    """Fenêtre Ctrl+9 harmonisée avec les fenêtres de résultats et pensée comme un chat."""
    ask_requested = pyqtSignal(list, str, object)

    WINDOW_WIDTH = 390
    MIN_HEIGHT = 80
    MAX_HEIGHT = 620
    MAX_RESPONSE_HEIGHT = 440

    def __init__(self, parent=None):
        super().__init__(parent)
        self.host = parent
        self.setWindowTitle("Assistant IA")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setFixedWidth(self.WINDOW_WIDTH)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.paths = []
        self.page_selections = {}
        self._drag_position = None
        self._header_press_pos = None
        self._header_was_dragged = False
        self.audio_thread = None
        self.is_recording = False
        self.is_collapsed = False
        self.expanded_height = self.MIN_HEIGHT
        self.collapse_animation = None
        self.turns = []
        self.current_turn_index = -1
        # Références conservées pendant le streaming Ctrl+9. La bulle courante
        # est mise à jour en place au lieu de reconstruire toute la conversation.
        self.current_assistant_bubble = None
        self.streaming_response_active = False
        # Le rendu des fragments SSE est regroupé pour éviter de détruire et
        # reconstruire toute la conversation à chaque token.
        self.pending_stream_render = False
        self.stream_render_timer = QTimer(self)
        self.stream_render_timer.setSingleShot(True)
        self.stream_render_timer.setInterval(45)
        self.stream_render_timer.timeout.connect(self._flush_stream_render)
        self._temp_files = set()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cleanup_temp_files)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{ background: transparent; }}
            QToolTip {{
                background-color: #FFFFFF;
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 0px;
                padding: 5px 8px;
                font-family: {FONT_TEXT};
                font-size: {SIZE_MD};
            }}
            QFrame#DocPanel {{
                background-color: {COLOR_BG_ACRYLIC};
                border: 1px solid {COLOR_BORDER_ACRYLIC};
                border-radius: {RADIUS_2XL};
            }}
            QFrame#DocHeader {{ background: transparent; border: none; }}
            QLabel {{ background: transparent; color: {COLOR_TEXT_PRIMARY}; border: none;
                     font-family: {FONT_TEXT}; font-size: {SIZE_MD}; }}
            QLabel#DocTitle {{ font-family: {FONT_DISPLAY};
                              font-size: {SIZE_LG}; font-weight: 700; }}
            QFrame#Composer {{
                background: rgba(255, 255, 255, 135);
                border: 1px solid rgba(0, 0, 0, 35);
                border-radius: {RADIUS_XL};
            }}
            QFrame#DocumentCard {{
                /* Les pièces jointes appartiennent visuellement au même bloc
                   que le champ « Message assistant IA ». */
                background: transparent;
                border: none;
                border-radius: 0;
            }}
            QLabel#Preview {{ background: rgba(255, 255, 255, 100); border: 1px solid rgba(0, 0, 0, 30);
                             border-radius: {RADIUS_MD}; padding: 3px; }}
            QTextEdit {{ background: transparent; border: none; padding: 6px 1px 4px 1px;
                        color: {COLOR_TEXT_PRIMARY}; font-family: {FONT_TEXT}; font-size: {SIZE_MD}; }}
            QTextBrowser#Response {{ background: transparent; border: none; padding: 0;
                                    font-family: {FONT_TEXT}; font-size: {SIZE_MD}; }}
            QPushButton#HeaderIconButton, QPushButton#ActionIconButton {{
                background: transparent; border: none; border-radius: {RADIUS_XL}; padding: 0; margin: 0;
            }}
            QPushButton#HeaderIconButton:hover, QPushButton#ActionIconButton:hover,
            QPushButton#HeaderIconButton:pressed, QPushButton#ActionIconButton:pressed {{
                background: {COLOR_HOVER_DARK}; border: none;
            }}
            QPushButton#MicRecording {{ background: rgba(198, 40, 40, 35); border: none; border-radius: {RADIUS_XL}; }}
            QScrollBar:vertical {{ background: {COLOR_SCROLLBAR_TRACK}; width: 6px; margin: 0; border-radius: 3px; }}
            QScrollBar::handle:vertical {{ background: {COLOR_SCROLLBAR_THUMB}; min-height: 26px; border-radius: 3px; }}
            QScrollBar::handle:vertical:hover {{ background: {COLOR_SCROLLBAR_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: transparent; border: none; }}
        """)
        outer = QVBoxLayout(self); outer.setContentsMargins(1,1,1,1); outer.setSpacing(0)
        self.panel = QFrame(); self.panel.setObjectName("DocPanel"); outer.addWidget(self.panel)
        root = QVBoxLayout(self.panel); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        header = QFrame(); header.setObjectName("DocHeader"); header.setFixedHeight(36)
        header.mousePressEvent=self._header_press; header.mouseMoveEvent=self._header_move; header.mouseReleaseEvent=self._header_release
        header_layout=QHBoxLayout(header); header_layout.setContentsMargins(9,1,3,0); header_layout.setSpacing(3)
        icon=QLabel(); icon.setFixedSize(18,18); icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(get_logo_pixmap(16, APP_DIR))
        title=QLabel("Assistant IA"); title.setObjectName("DocTitle")
        header_layout.addWidget(icon); header_layout.addWidget(title,1)
        close = AnimatedHeaderButton(ICONS_DARK["close"], "Fermer", header)
        close.clicked.connect(self.reject)
        header_layout.addWidget(close); root.addWidget(header)

        self.header_separator=QFrame(); self.header_separator.setFixedHeight(1); self.header_separator.setStyleSheet("background:rgba(0,0,0,35);border:none;")
        root.addWidget(self.header_separator)
        self.content_widget=QWidget(); content=QVBoxLayout(self.content_widget); content.setContentsMargins(10,4,10,10); content.setSpacing(4)

        self.drop_zone=QPushButton(self.content_widget); self.drop_zone.setObjectName("ActionIconButton")
        self.drop_zone.setIcon(create_svg_icon('<path d="M12 5v14M5 12h14"/>','#111111',1.8)); self.drop_zone.setIconSize(QSize(20,20)); self.drop_zone.setFixedHeight(42)
        self.drop_zone.setToolTip("Ajouter un PDF ou une image"); self.drop_zone.setCursor(Qt.PointingHandCursor); self.drop_zone.clicked.connect(self._choose_files)
        self.drop_zone.hide()

        # Bandeau unique des pièces jointes dans le bloc « Message assistant IA ».
        self.document_area=QFrame(); self.document_area.setObjectName("DocumentCard")
        area_layout=QVBoxLayout(self.document_area); area_layout.setContentsMargins(0,0,0,0); area_layout.setSpacing(0)
        self.image_scroll=QScrollArea(self.document_area)
        self.image_scroll.setWidgetResizable(False); self.image_scroll.setFrameShape(QFrame.NoFrame)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # La hauteur inclut les vignettes et, pour les PDF, la ligne des pages.
        # La barre horizontale est réservée par Qt uniquement si le contenu
        # dépasse réellement la largeur disponible dans le compositeur.
        self.image_scroll.setFixedHeight(130)
        self.image_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}"
            "QScrollBar:horizontal{height:7px;background:transparent;margin:0 6px 1px 6px;}"
            "QScrollBar::handle:horizontal{background:rgba(82,91,102,115);border-radius:3px;min-width:24px;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;border:none;}"
            "QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{background:transparent;}"
        )
        self.image_strip=QWidget(); self.image_strip.setFixedHeight(116)
        self.image_strip_layout=QHBoxLayout(self.image_strip)
        self.image_strip_layout.setContentsMargins(6,6,6,2); self.image_strip_layout.setSpacing(10)
        self.image_strip_layout.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.image_scroll.setWidget(self.image_strip); area_layout.addWidget(self.image_scroll)
        self.document_area.hide()
        self.preview=QLabel(); self.filename=QLabel(); self.first_page=QLineEdit("1")
        self.last_page=QLineEdit("1"); self.page_info=QLabel()
        for legacy_widget in (self.preview,self.filename,self.first_page,self.last_page,self.page_info): legacy_widget.hide()

        # Une vraie pile de widgets remplace le tableau HTML unique. Les QFrame
        # prennent correctement en charge border-radius, contrairement aux cellules
        # de tableau du moteur HTML de QTextDocument.
        self.response=QScrollArea(self.content_widget)
        self.response.setObjectName("Response")
        self.response.setWidgetResizable(True)
        self.response.setFrameShape(QFrame.NoFrame)
        self.response.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.response.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response.setStyleSheet(
            "QScrollArea#Response{background:transparent;border:none;padding:0;margin:0;}"
            "QScrollArea#Response>QWidget>QWidget{background:transparent;border:none;margin:0;padding:0;}"
            "QScrollArea#Response QScrollBar:vertical{margin:0;}"
        )
        # Aucun décalage interne : le bord gauche des bulles assistant est sur
        # le même axe que le bord gauche du compositeur « Message assistant IA ».
        # La barre verticale couvre exactement la hauteur de la conversation.
        self.response.setViewportMargins(0, 0, 0, 0)
        self.conversation_widget=QWidget()
        self.conversation_widget.setStyleSheet("background:transparent;border:none;")
        self.conversation_layout=QVBoxLayout(self.conversation_widget)
        # La conversation commence sur le même axe gauche que le compositeur.
        # La marge des messages utilisateur est gérée à droite de leur ligne.
        self.conversation_layout.setContentsMargins(0,0,0,0)
        self.conversation_layout.setSpacing(10)
        self.conversation_layout.setAlignment(Qt.AlignTop)
        self.response.setWidget(self.conversation_widget)
        self.response.setMinimumHeight(0)
        self.response.setMaximumHeight(self.MAX_RESPONSE_HEIGHT)
        self.response.hide()
        content.addWidget(self.response,1)

        self.status=QLabel("", self.content_widget)
        self.status.setStyleSheet(f"color:{COLOR_PRIMARY}; font-family:{FONT_TEXT}; font-size:{SIZE_SM}; font-style:italic; padding:2px 4px;")
        self.status.setTextFormat(Qt.PlainText)
        self.status.hide()
        content.addWidget(self.status)

        self.composer=QFrame(); self.composer.setObjectName("Composer"); self.composer.setMinimumHeight(38); self.composer.setAcceptDrops(True); self.composer.installEventFilter(self)
        composer_outer=QVBoxLayout(self.composer); composer_outer.setContentsMargins(4,2,4,2); composer_outer.setSpacing(2)
        composer_outer.addWidget(self.document_area)
        composer_layout=QHBoxLayout(); composer_layout.setContentsMargins(0,0,0,0); composer_layout.setSpacing(0)
        self.add_button=AnimatedComposerButton("add"); self.add_button.setToolTip("Ajouter un PDF ou une image"); self.add_button.clicked.connect(self._choose_files)
        self.question=MessageTextEdit(); self.question.setPlaceholderText("Message assistant IA"); self.question.setFixedHeight(30); self.question.setContentsMargins(0,0,0,0); self.question.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.question.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.question.document().setDocumentMargin(0)
        self.question.setViewportMargins(0,0,0,0)
        self.question.setStyleSheet(f"QTextEdit{{background:transparent;border:none;padding:8px 1px 0 1px;color:{COLOR_TEXT_PRIMARY};font-family:{FONT_TEXT};font-size:{SIZE_MD};}}")
        self.question.verticalScrollBar().setValue(0)
        self.question.setAcceptDrops(False)
        self.question.viewport().setAcceptDrops(False)
        self.audio_bars=ScrollingAudioBars(self.composer)
        self.mic_icon=create_svg_icon('<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8"/>',COLOR_TEXT_PRIMARY,1.7)
        self.recording_icon=create_svg_icon('<circle cx="12" cy="12" r="6" fill="#D13438" stroke="none"/>',COLOR_DANGER,1.0)
        self.mic=AnimatedComposerButton("mic"); self.mic.setToolTip("Dicter"); self.mic.clicked.connect(self._toggle_microphone)
        # Le bouton d'envoi utilise le même composant, la même taille, la même
        # couleur et la même épaisseur de trait que le microphone.
        self.send=AnimatedComposerButton("send"); self.send.setToolTip("Envoyer"); self.send.clicked.connect(self._ask_text); self.send.hide()
        # Pendant la génération, ce carré remplace le micro et l'envoi. Il utilise
        # exactement le même dessin que le bouton d'arrêt de l'enregistrement audio.
        self.stop_generation_button=AnimatedComposerButton("stop")
        self.stop_generation_button.setToolTip("Arrêter la génération")
        self.stop_generation_button.clicked.connect(self._stop_llm_generation)
        self.stop_generation_button.hide()
        self.question.textChanged.connect(self._update_send_visibility)
        self.question.textChanged.connect(self._update_question_height)
        self.question.send_requested.connect(self._ask_text)
        self.question.pasted_files.connect(self._add_paths)
        composer_layout.addWidget(self.add_button); composer_layout.addWidget(self.question,1); composer_layout.addWidget(self.audio_bars,1); composer_layout.addWidget(self.mic); composer_layout.addWidget(self.send); composer_layout.addWidget(self.stop_generation_button)
        composer_outer.addLayout(composer_layout)
        self.drop_feedback=QLabel("Déposer pour ajouter le document",self.composer)
        self.drop_feedback.setAlignment(Qt.AlignCenter)
        self.drop_feedback.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        self.drop_feedback.setStyleSheet(f"QLabel{{background:{COLOR_PRIMARY_LIGHT};color:{COLOR_PRIMARY};border:2px solid {COLOR_PRIMARY};border-radius:{RADIUS_LG};font-family:{FONT_TEXT};font-size:{SIZE_MD};font-weight:700;}}")
        self.drop_feedback.hide()
        content.addWidget(self.composer)
        root.addWidget(self.content_widget,1)
        self._update_height()

    def _open_source_link(self, url):
        value = url.toString()
        if url.scheme().lower() == "file":
            if self.host is not None:
                self.host.open_response_link(value)
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
                self._show_source_image_large(
                    metadata.get("path", ""),
                    metadata.get("title", "Source surlignée"),
                )
            except (ValueError, UnicodeDecodeError):
                pass
            return
        if self.host is None:
            return
        match=re.match(r"^source:(\d+):([A-Za-z0-9_-]+)$",value)
        if not match:
            return
        try:
            token=match.group(2); padding="="*(-len(token)%4); filename=base64.urlsafe_b64decode((token+padding).encode("ascii")).decode("utf-8")
            self.host.open_document_source(filename,int(match.group(1)))
        except (ValueError,UnicodeDecodeError):
            return

    def _show_source_image_large(self, image_path, source_title="Source surlignée"):
        """Affiche la capture à un tiers de la taille x2 précédente."""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        # La fenêtre précédente affichait 2 fois la taille de la capture.
        # On divise cette taille par 3, soit 2/3 de la capture originale.
        target_width = max(1, round(pixmap.width() * 2 / 3))
        target_height = max(1, round(pixmap.height() * 2 / 3))
        zoomed = pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(source_title)
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        dialog.setStyleSheet(
            f"QDialog{{background:{COLOR_BG_PAGE};}}"
            f"QScrollArea{{background:{COLOR_BG_PAGE};border:none;}}"
            f"QLabel{{background:{COLOR_BG_SURFACE};border:none;}}"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        label = QLabel()
        label.setPixmap(zoomed)
        label.setFixedSize(zoomed.size())
        scroll.setWidget(label)
        layout.addWidget(scroll)

        # La fenêtre épouse l'image zoomée. Si elle dépasse l'écran, elle est
        # limitée à la zone disponible et les barres de défilement prennent le relais.
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        frame_extra_width = 24
        frame_extra_height = 54
        target_width = zoomed.width() + 20 + frame_extra_width
        target_height = zoomed.height() + 20 + frame_extra_height
        dialog.resize(
            min(target_width, available.width() - 30),
            min(target_height, available.height() - 30),
        )
        dialog.exec_()

    def _answer_without_sources(self, answer):
        if not answer:
            return ""
        clean = re.split(r"(?im)^\s*#{2,3}\s*Sources\s*$", answer, maxsplit=1)[0]
        clean = re.split(r"(?im)^\s*Sources\s*:\s*$", clean, maxsplit=1)[0]
        return clean.rstrip()

    def _attachment_preview_html(self, documents):
        """Crée les vignettes à conserver dans la bulle de la demande utilisateur."""
        cards = []
        for index, document in enumerate(documents or []):
            path = document.get("path") if isinstance(document, dict) else document
            if not path or not os.path.isfile(path):
                continue
            pages = document.get("pages", []) if isinstance(document, dict) else []
            is_pdf = path.lower().endswith(".pdf")
            preview_path = path
            page_caption = ""

            if is_pdf:
                first = int(pages[0]) if pages else 1
                last = int(pages[-1]) if pages else first
                page_caption = str(first) if first == last else f"{first} - {last}"
                if fitz is not None:
                    try:
                        doc = fitz.open(path)
                        try:
                            page_number = max(1, min(first, doc.page_count))
                            pix = doc.load_page(page_number - 1).get_pixmap(
                                matrix=fitz.Matrix(1.0, 1.0), alpha=False
                            )
                            preview_path = os.path.join(
                                tempfile.gettempdir(),
                                f"assistant_turn_attachment_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
                            )
                            pix.save(preview_path)
                            self._temp_files.add(preview_path)
                        finally:
                            doc.close()
                    except Exception:
                        LOGGER.exception("Impossible de générer la vignette jointe du PDF")
                        preview_path = ""

            if not preview_path or not os.path.isfile(preview_path):
                continue

            pixmap = QPixmap(preview_path)
            if pixmap.isNull():
                continue
            # Une vignette de document et sa ligne de pages ont la même hauteur
            # totale qu'une vignette d'image seule.
            total_h = 76
            caption_h = 16 if is_pdf else 0
            image_h = total_h - caption_h
            shown = pixmap.scaled(76, image_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rendered_path = os.path.join(
                tempfile.gettempdir(),
                f"assistant_turn_rendered_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
            )
            rounded = QPixmap(shown.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing, True)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(rounded.rect()), 7, 7)
            painter.setClipPath(clip)
            painter.drawPixmap(0, 0, shown)
            painter.end()
            rounded.save(rendered_path, "PNG")
            self._temp_files.add(rendered_path)
            uri = Path(rendered_path).as_uri()

            caption = (
                f'<div style="height:{caption_h}px; line-height:{caption_h}px; '
                f'text-align:center; font-size:10px; color:#52677C;">'
                f'{html.escape(page_caption)}</div>'
                if is_pdf else ""
            )
            cards.append(
                '<td valign="top" style="padding-right:8px;">'
                f'<div style="width:82px; height:{total_h}px; text-align:center;">'
                f'<div style="height:{image_h}px; line-height:{image_h}px;">'
                f'<img src="{uri}" /></div>{caption}</div></td>'
            )

        if not cards:
            return ""
        return (
            '<div style="margin-top:8px; overflow:hidden;">'
            '<table cellspacing="0" cellpadding="0" border="0"><tr>'
            + "".join(cards)
            + '</tr></table></div>'
        )

    def _take_current_attachments(self):
        """Fige les pièces jointes pour le tour puis vide immédiatement le compositeur."""
        documents = self._specs()
        attachments_html = self._attachment_preview_html(documents)
        self.paths.clear()
        self.page_selections.clear()
        self._show_document(-1)
        return documents, attachments_html

    def _clear_conversation_widgets(self):
        while self.conversation_layout.count():
            item = self.conversation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_conversation(self):
        self._clear_conversation_widgets()
        self.current_assistant_bubble = None
        if not self.turns:
            self.response.hide()
            return
        available = max(180, self.width() - 34)
        bubble_width = max(140, available - 50)
        for turn_index, turn in enumerate(self.turns):
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
            user_row = QWidget(self.conversation_widget)
            user_row.setStyleSheet("background:transparent;border:none;")
            user_layout = QHBoxLayout(user_row)
            user_layout.setContentsMargins(0, 0, 8, 0)
            user_layout.setSpacing(0)
            user_bubble = ChatBubble("user", user_row)
            # Les pièces jointes sont affichées avant la question, comme dans le
            # compositeur, puis la bulle épouse le contenu et reste alignée à droite.
            user_bubble.set_html(turn.get("attachments_html", "") + question)
            user_bubble.fit_to_content_width(bubble_width)
            user_layout.addStretch(1)
            user_layout.addWidget(user_bubble, 0, Qt.AlignRight | Qt.AlignTop)
            self.conversation_layout.addWidget(user_row)

            answer = self._answer_without_sources(turn.get("answer", ""))
            if turn.get("loading", False) and not answer:
                assistant_row = QWidget(self.conversation_widget)
                assistant_row.setStyleSheet("background:transparent;border:none;")
                assistant_layout = QHBoxLayout(assistant_row)
                assistant_layout.setContentsMargins(0, 0, 50, 0)
                assistant_layout.setSpacing(0)
                thinking_bubble = ChatBubble("assistant", assistant_row)
                thinking_bubble.setFixedWidth(78)
                thinking_bubble.browser.hide()
                dots = ThinkingDots(thinking_bubble)
                thinking_bubble.layout().addWidget(dots, 0, Qt.AlignLeft | Qt.AlignVCenter)
                thinking_bubble.setFixedHeight(44)
                assistant_layout.addWidget(thinking_bubble, 0, Qt.AlignLeft | Qt.AlignTop)
                assistant_layout.addStretch(1)
                self.conversation_layout.addWidget(assistant_row)
            if answer:
                rendered = (
                    self.host.markdown_to_html(answer)
                    if self.host is not None
                    else html.escape(answer).replace("\n", "<br>")
                )
                assistant_row = QWidget(self.conversation_widget)
                assistant_row.setStyleSheet("background:transparent;border:none;")
                assistant_layout = QHBoxLayout(assistant_row)
                assistant_layout.setContentsMargins(0, 0, 50, 0)
                assistant_layout.setSpacing(0)
                assistant_bubble = ChatBubble("assistant", assistant_row)
                assistant_bubble.setFixedWidth(bubble_width)
                assistant_bubble.link_clicked.connect(self._open_source_link)
                assistant_bubble.set_html(rendered + turn.get("sources_html", ""))
                if turn_index == self.current_turn_index:
                    self.current_assistant_bubble = assistant_bubble
                assistant_layout.addWidget(assistant_bubble, 1)
                self.conversation_layout.addWidget(assistant_row)
        self.response.show()
        self.conversation_widget.adjustSize()
        QTimer.singleShot(0, self._update_height)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar=self.response.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_height(self):
        self.layout().activate()
        self.composer.layout().activate()
        self.content_widget.layout().activate()

        response_h = 0
        if self.response.isVisible():
            self.conversation_layout.activate()
            doc_h = self.conversation_layout.sizeHint().height() + 4
            if self.streaming_response_active:
                # Une hauteur stable évite la recomposition répétée de la fenêtre
                # translucide/Acrylic pendant l'arrivée des tokens.
                response_h = self.MAX_RESPONSE_HEIGHT
            else:
                response_h = max(45, min(self.MAX_RESPONSE_HEIGHT, doc_h))
            self.response.setFixedHeight(response_h)
        else:
            self.response.setFixedHeight(0)

        # The response and composer are stacked vertically. Computing the height
        # explicitly avoids the conversation being painted behind the composer.
        header_h = 36
        separator_h = 1 if self.header_separator.isVisible() else 0
        top_bottom_margins = 14
        content_spacing = 4 if response_h else 0
        composer_h = max(38, self.composer.sizeHint().height())
        target = header_h + separator_h + top_bottom_margins + content_spacing + response_h + composer_h + 2
        target = max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, target))

        if not self.is_collapsed and abs(self.height() - target) > 2:
            self.setFixedHeight(target)
            self.expanded_height = target

    def _add_sources_html(self, answer, documents):
        if fitz is None or not answer.strip(): return ""
        by_name={}
        for document in documents:
            path=document.get("path") if isinstance(document,dict) else document
            if path: by_name[os.path.basename(path).casefold()]=path
        citations=re.findall(r"([^\n/\\]+?\.pdf)\s*[—-]\s*(?:p(?:age)?\.?\s*)?(\d+)(?:\s*\n+\s*>?\s*(?:Extrait\s*:\s*)?([^\n]+))?",answer,re.IGNORECASE)
        cards=[]
        for index,(filename,page_text,excerpt) in enumerate(citations):
            path=by_name.get(os.path.basename(filename.strip()).casefold())
            if not path: continue
            try:
                doc=fitz.open(path); total=doc.page_count; page_number=max(1,int(page_text))
                if page_number>total: doc.close(); continue
                page=doc.load_page(page_number-1); needle=excerpt.strip().strip(" \t\r\n\"'«»"); rects=page.search_for(needle) if len(needle)>=8 else []
                if not rects and len(needle)>80: rects=page.search_for(needle[:80])
                clip=page.rect
                if rects:
                    union=fitz.Rect(rects[0])
                    for rect in rects[1:]: union|=rect
                    clip=fitz.Rect(max(page.rect.x0,union.x0-28),max(page.rect.y0,union.y0-42),min(page.rect.x1,union.x1+28),min(page.rect.y1,union.y1+42))
                    highlight=page.add_highlight_annot(rects); highlight.set_colors(stroke=(0.55, 0.92, 0.66)); highlight.update()
                # Conserve une capture haute définition distincte pour la loupe
                # et la fenêtre x2. Les anciens tours ne sont plus écrasés car le
                # nom contient un identifiant unique par capture.
                capture_id = f"{time.monotonic_ns()}_{index}"
                pix=page.get_pixmap(matrix=fitz.Matrix(3.0,3.0),clip=clip,alpha=False,annots=True)
                image_path=os.path.join(tempfile.gettempdir(),f"assistant_source_{os.getpid()}_{capture_id}.png")
                pix.save(image_path); doc.close()
                self._temp_files.add(image_path)
                source_pixmap=QPixmap(image_path)
                max_w=max(120,self.width()-82)
                display_w=min(source_pixmap.width(), max_w)
                display_h=max(1, round(source_pixmap.height() * display_w / max(1, source_pixmap.width())))
                token=base64.urlsafe_b64encode(os.path.basename(path).encode("utf-8")).decode("ascii").rstrip("=")
                href=f"source:{page_number}:{token}"; uri=Path(image_path).as_uri(); title=html.escape(os.path.splitext(os.path.basename(path))[0])
                source_title = f"{os.path.splitext(os.path.basename(path))[0]} (Page {page_number}/{total})"
                image_payload = json.dumps(
                    {"path": image_path, "title": source_title},
                    ensure_ascii=False,
                ).encode("utf-8")
                image_token = base64.urlsafe_b64encode(image_payload).decode("ascii").rstrip("=")
                image_href = f"sourceimage:{image_token}"
                cards.append(
                    f'<div style="margin-top:12px; padding-top:9px; border-top:1px solid #C9E8D3;">'
                    f'<div style="font-size:10px; font-style:italic; color:#526B5B;">'
                    f'Source : <a href="{href}" style="color:#397D58; text-decoration:none;">'
                    f'{title} (Page {page_number}/{total})</a></div>'
                    # Le navigateur affiche la capture réduite via width/height,
                    # mais conserve le fichier haute définition comme ressource.
                    # La loupe x2 prélève donc directement des pixels nets.
                    f'<div style="margin-top:8px;"><a href="{image_href}">'
                    f'<img src="{uri}" width="{display_w}" height="{display_h}" />'
                    f'</a></div></div>'
                )
            except Exception: LOGGER.exception("Impossible de générer la capture de la source")
        if not cards: return ""
        return ''.join(cards)

    def show_source_captures(self, answer, documents):
        if not self.turns: return
        sources=self._add_sources_html(answer,documents)
        if sources:
            self.turns[-1]["sources_html"]=sources
            self._render_conversation()

    def _header_press(self,event):
        if event.button()==Qt.LeftButton:
            self._drag_position=event.globalPos()-self.frameGeometry().topLeft(); self._header_press_pos=event.globalPos(); self._header_was_dragged=False; event.accept()
    def _header_move(self,event):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            if self._header_press_pos is not None and (event.globalPos()-self._header_press_pos).manhattanLength()>QApplication.startDragDistance(): self._header_was_dragged=True
            if self._header_was_dragged: self.move(event.globalPos()-self._drag_position)
            event.accept()
    def _header_release(self,event):
        if event.button()==Qt.LeftButton:
            if not self._header_was_dragged: self.toggle_collapse()
            self._drag_position=None; self._header_press_pos=None; self._header_was_dragged=False; event.accept()

    def toggle_collapse(self):
        if self.collapse_animation is not None:
            self.collapse_animation.stop()
            self.collapse_animation.deleteLater()
            self.collapse_animation = None

        current = self.height()
        collapsed_height = 38
        self.setMinimumHeight(collapsed_height)
        if self.is_collapsed:
            target = max(self.MIN_HEIGHT, self.expanded_height)
            self.header_separator.show()
            self.content_widget.show()
            expanding = True
        else:
            self.expanded_height = max(self.MIN_HEIGHT, current)
            self.header_separator.hide()
            target = collapsed_height
            expanding = False

        animation = QPropertyAnimation(self, b"geometry", self)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(self.geometry())
        animation.setEndValue(QRect(self.x(), self.y(), self.width(), target))
        self.collapse_animation = animation

        def done():
            if self.collapse_animation is not animation:
                return
            self.collapse_animation = None
            self.is_collapsed = not expanding
            if expanding:
                self.setMinimumHeight(self.MIN_HEIGHT)
            else:
                self.content_widget.hide()
            animation.deleteLater()

        animation.finished.connect(done)
        animation.start()

    def focus_message_input(self):
        """Place immédiatement le curseur dans « Message assistant IA »."""
        if self.is_collapsed:
            self.toggle_collapse()
        self.raise_()
        self.activateWindow()
        self.question.setFocus(Qt.ShortcutFocusReason)
        cursor = self.question.textCursor()
        cursor.movePosition(cursor.End)
        self.question.setTextCursor(cursor)

    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self._apply_effects)
        QTimer.singleShot(0,self._update_height)
        QTimer.singleShot(0,self.focus_message_input)
    def _apply_effects(self):
        try: apply_acrylic_blur(int(self.winId()),0xB8F5F5F5); apply_rounded_corners(int(self.winId()))
        except Exception: pass

    def _update_question_height(self):
        """Agrandit la saisie jusqu'à trois lignes, puis active son défilement."""
        document = self.question.document()
        document.setTextWidth(max(40, self.question.viewport().width()))
        line_height = max(14, self.question.fontMetrics().lineSpacing())
        minimum_height = 30
        maximum_height = minimum_height + 2 * line_height
        content_height = int(document.size().height()) + 8
        target_height = max(minimum_height, min(maximum_height, content_height))
        self.question.setFixedHeight(target_height)
        self.question.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if content_height > maximum_height else Qt.ScrollBarAlwaysOff
        )
        if content_height > maximum_height:
            bar = self.question.verticalScrollBar()
            bar.setValue(bar.maximum())
        self._update_height()

    def _update_send_visibility(self):
        """Affiche une seule action adaptée à l'état du compositeur."""
        if self.streaming_response_active:
            self.mic.hide()
            self.send.hide()
            self.stop_generation_button.show()
            return
        self.stop_generation_button.hide()
        if self.is_recording:
            self.mic.show()
            self.send.hide()
            return
        has_text = bool(self.question.toPlainText().strip())
        self.mic.setVisible(not has_text)
        self.send.setVisible(has_text)

    def _stop_llm_generation(self):
        """Arrête réellement la génération sans afficher de message intermédiaire."""
        if not self.streaming_response_active:
            return
        self.stop_generation_button.setEnabled(False)
        thread = self.host.document_thread if self.host is not None else None
        if thread is not None and thread.isRunning():
            thread.stop()
        else:
            self.finish_response()
    @staticmethod
    def _supported(path): return os.path.isfile(path) and os.path.splitext(path)[1].lower() in {".pdf",".png",".jpg",".jpeg",".webp",".bmp",".gif",".tif",".tiff"}
    def _dragged_paths(self,event):
        if not event.mimeData().hasUrls(): return []
        return [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and self._supported(u.toLocalFile())]
    def _set_drop_feedback(self,visible):
        if visible:
            self.drop_feedback.setGeometry(1,1,max(1,self.composer.width()-2),max(1,self.composer.height()-2))
            self.drop_feedback.show(); self.drop_feedback.raise_()
        else:self.drop_feedback.hide()
    def eventFilter(self,watched,event):
        if watched is self.composer:
            if event.type() in (QEvent.DragEnter,QEvent.DragMove):
                paths=self._dragged_paths(event); self._set_drop_feedback(bool(paths))
                if paths: event.acceptProposedAction(); return True
            elif event.type()==QEvent.DragLeave:
                self._set_drop_feedback(False); event.accept(); return True
            elif event.type()==QEvent.Drop:
                paths=self._dragged_paths(event); self._set_drop_feedback(False)
                if paths: self._add_paths(paths); event.acceptProposedAction(); return True
        return super().eventFilter(watched,event)
    def dragEnterEvent(self,event):
        paths=self._dragged_paths(event); self._set_drop_feedback(bool(paths))
        if paths:event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):
        if self._dragged_paths(event):self._set_drop_feedback(True); event.acceptProposedAction()
        else:event.ignore()
    def dragLeaveEvent(self,event):
        self._set_drop_feedback(False); event.accept()
    def dropEvent(self,event):
        paths=self._dragged_paths(event); self._set_drop_feedback(False)
        if paths:self._add_paths(paths); event.acceptProposedAction()
        else:event.ignore()
    def _choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Ajouter des documents","","Documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        self._add_paths(paths)
    def _page_count(self,path):
        if path.lower().endswith('.pdf') and fitz is not None:
            doc=fitz.open(path)
            try:return max(1,doc.page_count)
            finally:doc.close()
        return 1
    def _add_paths(self,paths):
        for path in paths:
            path=os.path.abspath(path)
            if self._supported(path) and path not in self.paths:
                count=self._page_count(path); self.paths.append(path); self.page_selections[path]=(1,count)
        if self.paths:self._show_document(len(self.paths)-1)
    def _clear_image_strip(self):
        while self.image_strip_layout.count():
            w=self.image_strip_layout.takeAt(0).widget()
            if w:w.deleteLater()
    def _remove_path(self,path):
        if path in self.paths:self.paths.remove(path); self.page_selections.pop(path,None)
        self._show_document(len(self.paths)-1)
    def _rebuild_image_strip(self):
        """Affiche chaque pièce jointe dans une carte à contour gris arrondi."""
        self._clear_image_strip()
        cell_w, cell_h = 104, 110
        preview_w, pdf_preview_h = 86, 66
        pdf_title_y, pdf_title_h = 68, 15
        page_row_y, page_row_h = 82, 25

        for path in self.paths:
            is_pdf = path.lower().endswith('.pdf')
            holder = AttachmentPreviewWidget(self.image_strip)
            holder.setFixedSize(cell_w, cell_h)
            if is_pdf:
                count = self._page_count(path)
                first, last = self.page_selections.get(path, (1, count))
                source = QPixmap()
                if fitz is not None:
                    try:
                        doc = fitz.open(path)
                        try:
                            pix = doc.load_page(max(0, first - 1)).get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                            source.loadFromData(pix.tobytes('png'))
                        finally:
                            doc.close()
                    except Exception:
                        LOGGER.exception("Impossible de générer la vignette PDF")
                if source.isNull():
                    source = QPixmap(preview_w, pdf_preview_h - 6); source.fill(QColor('#EEF3F8'))
                shown = source.scaled(preview_w, pdf_preview_h - 6, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = (cell_w - shown.width()) // 2
                y = 4 + max(0, (pdf_preview_h - 6 - shown.height()) // 2)
                rounded = QPixmap(shown.size()); rounded.fill(Qt.transparent)
                painter = QPainter(rounded); painter.setRenderHint(QPainter.Antialiasing, True)
                clip = QPainterPath(); clip.addRoundedRect(QRectF(rounded.rect()), 6, 6)
                painter.setClipPath(clip); painter.drawPixmap(0, 0, shown); painter.end()
                label = QLabel(holder); label.setPixmap(rounded); label.setGeometry(x, y, shown.width(), shown.height())

                pdf_name = Path(path).stem
                displayed_name = pdf_name if len(pdf_name) <= 12 else pdf_name[:12] + "..."
                name_label = QLabel(displayed_name, holder)
                name_label.setGeometry(4, pdf_title_y, cell_w - 8, pdf_title_h)
                name_label.setAlignment(Qt.AlignCenter); name_label.setToolTip(pdf_name)
                name_label.setStyleSheet(f"QLabel{{background:transparent;border:none;color:{COLOR_TEXT_SECONDARY};font-family:{FONT_TEXT};font-size:{SIZE_XS};font-weight:600;padding:0;margin:0;}}")

                pages = QWidget(holder); pages.setGeometry(0, page_row_y, cell_w, page_row_h)
                row = QHBoxLayout(pages); row.setContentsMargins(15, 0, 15, 1); row.setSpacing(0)
                first_edit, last_edit = QLineEdit(str(first)), QLineEdit(str(last))
                for edit in (first_edit, last_edit):
                    edit.setAlignment(Qt.AlignCenter); edit.setFixedSize(24, 19)
                    edit.setStyleSheet(f"QLineEdit{{background:transparent;border:1px solid transparent;border-radius:{RADIUS_SM};padding:0;margin:0;font-family:{FONT_TEXT};font-size:{SIZE_XS};}}QLineEdit:hover{{background:rgba(255,255,255,175);border:1px solid rgba(0,0,0,45);}}QLineEdit:focus{{background:#FFFFFF;border:1px solid rgba(0,0,0,70);}}")
                dash = QLabel("-"); dash.setAlignment(Qt.AlignCenter); dash.setFixedSize(10, 19)
                dash.setStyleSheet(f"QLabel{{background:transparent;border:none;padding:0;margin:0;font-family:{FONT_TEXT};font-size:{SIZE_XS};}}")
                row.addStretch(1); row.addWidget(first_edit); row.addWidget(dash); row.addWidget(last_edit); row.addStretch(1)
                def save_range(_path=path, _first=first_edit, _last=last_edit):
                    total = self._page_count(_path)
                    try: a, b = int(_first.text()), int(_last.text())
                    except ValueError: a, b = self.page_selections.get(_path, (1, total))
                    a = max(1, min(a, total)); b = max(a, min(b, total))
                    self.page_selections[_path] = (a, b); self._rebuild_image_strip(); self._update_height()
                first_edit.editingFinished.connect(save_range); last_edit.editingFinished.connect(save_range)
            else:
                source = QPixmap(path)
                if source.isNull(): holder.deleteLater(); continue
                shown = source.scaled(preview_w, cell_h - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                rounded = QPixmap(shown.size()); rounded.fill(Qt.transparent)
                painter = QPainter(rounded); painter.setRenderHint(QPainter.Antialiasing, True)
                clip = QPainterPath(); clip.addRoundedRect(QRectF(rounded.rect()), 7, 7)
                painter.setClipPath(clip); painter.drawPixmap(0, 0, shown); painter.end()
                x, y = (cell_w - shown.width()) // 2, (cell_h - shown.height()) // 2
                label = QLabel(holder); label.setPixmap(rounded); label.setGeometry(x, y, shown.width(), shown.height())
            close = QPushButton("×", holder); close.setFixedSize(20, 20); close.move(cell_w - 22, 2)
            close.setCursor(Qt.PointingHandCursor)
            close.setStyleSheet(f"QPushButton{{background:{COLOR_GRAY_500};color:white;border:1px solid {COLOR_BORDER};border-radius:10px;padding:0;font-size:15px;font-weight:600;}}QPushButton:hover{{background:{COLOR_GRAY_700};}}")
            close.clicked.connect(lambda _=False, p=path: self._remove_path(p)); holder.set_close_button(close)
            self.image_strip_layout.addWidget(holder)

        margins = self.image_strip_layout.contentsMargins(); spacing = self.image_strip_layout.spacing()
        total_width = margins.left() + margins.right() + len(self.paths) * cell_w + max(0, len(self.paths) - 1) * spacing
        self.image_strip.setFixedSize(max(1, total_width), 116)
        self.image_scroll.setVisible(bool(self.paths)); self.document_area.setVisible(bool(self.paths))
        self.image_strip.adjustSize(); self.image_scroll.viewport().updateGeometry()

    def _show_document(self,index=-1):
        if not self.paths:
            self._clear_image_strip(); self.image_scroll.hide(); self.document_area.hide(); self.status.hide(); self._update_height(); return
        self._rebuild_image_strip(); self.status.setText("Pièces jointes prêtes"); self._update_height()
    def _save_page_range(self):
        return
    def _remove_current(self):
        if self.paths:
            path=self.paths.pop(); self.page_selections.pop(path,None); self._show_document(len(self.paths)-1)
    def _specs(self):
        return [{"path":p,"pages":list(range(self.page_selections[p][0],self.page_selections[p][1]+1))} for p in self.paths]

    def begin_response(self, question, attachments_html=""):
        self.streaming_response_active = True
        self.current_assistant_bubble = None
        self.turns.append({
            "question": question,
            "answer": "",
            "sources_html": "",
            "attachments_html": attachments_html,
            "loading": True,
        })
        self.current_turn_index = len(self.turns) - 1
        self.response.show()
        self._render_conversation()
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
    def append_response(self,text):
        if self.current_turn_index < 0:
            return
        turn = self.turns[self.current_turn_index]
        turn["answer"] += text
        # Dès le premier fragment, les points disparaissent. Le rendu est ensuite
        # limité à environ 22 mises à jour par seconde pour supprimer scintillement,
        # sauts de largeur et pertes temporaires de la barre de défilement.
        turn["loading"] = False
        self.pending_stream_render = True
        if not self.stream_render_timer.isActive():
            self.stream_render_timer.start()

    def _flush_stream_render(self):
        if not self.pending_stream_render:
            return
        self.pending_stream_render = False
        if self.current_turn_index < 0:
            return
        turn = self.turns[self.current_turn_index]
        answer = self._answer_without_sources(turn.get("answer", ""))
        rendered = (
            self.host.markdown_to_html(answer)
            if self.host is not None
            else html.escape(answer).replace("\n", "<br>")
        )
        try:
            bubble_is_valid = (
                self.current_assistant_bubble is not None
                and self.current_assistant_bubble.parent() is not None
            )
        except RuntimeError:
            bubble_is_valid = False
        if not bubble_is_valid:
            # Premier fragment uniquement : remplace les points par la bulle.
            self._render_conversation()
        else:
            # Fragments suivants : mise à jour du QTextBrowser existant, sans
            # supprimer ni recréer les widgets de la conversation.
            self.current_assistant_bubble.set_html(
                rendered + turn.get("sources_html", "")
            )
            self.conversation_layout.activate()
            self.conversation_widget.adjustSize()
            self._scroll_to_bottom()

    def finish_response(self):
        self.streaming_response_active = False
        self.stream_render_timer.stop()
        self.pending_stream_render = False
        if self.current_turn_index>=0:
            self.turns[self.current_turn_index]["loading"]=False
        self.status.clear(); self.status.hide()
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
        self._render_conversation()
    def show_error(self,message):
        self.streaming_response_active = False
        if self.current_turn_index>=0:
            self.turns[self.current_turn_index]["loading"]=False; self.turns[self.current_turn_index]["answer"] += f"\n\n⚠️ {message}"
        self.status.setText("Erreur d'analyse")
        self.stop_generation_button.setEnabled(True)
        self._update_send_visibility()
        self._render_conversation()

    def _ask_text(self):
        question = self.question.toPlainText().strip()
        if not question:
            self.status.setText("Saisissez une question ou utilisez le microphone")
            return
        documents, attachments_html = self._take_current_attachments()
        self.begin_response(question, attachments_html)
        self.question.clear()
        self.ask_requested.emit(documents, question, None)
    def _set_inline_recording_visual(self,active):
        self.question.setVisible(not active)
        # Un clic pendant la dictée termine l'enregistrement puis envoie
        # l'audio. L'icône Envoyer correspond donc à l'action réelle.
        self.mic.kind="send" if active else "mic"
        self.mic.update()
        self.audio_bars.start() if active else self.audio_bars.stop()
        self._update_send_visibility()
        self._update_height()
    def _toggle_microphone(self):
        if self.is_recording:
            if self.audio_thread and self.audio_thread.isRunning():self.audio_thread.stop_recording()
            self.status.setText("Traitement de la question audio..."); return
        voice=self.host.config.get("voice_input",{}) if self.host else {}; self.is_recording=True; self._set_inline_recording_visual(True)
        device=self.host._selected_voice_device() if self.host else None
        self.audio_thread=AudioRecorderThread(device,voice.get("sample_rate",16000),voice.get("maximum_duration",60.0),release_tail_ms=voice.get("release_tail_ms",700),microphone_gain=voice.get("microphone_gain",2.0),parent=self)
        self.audio_thread.level_changed.connect(self.audio_bars.set_level); self.audio_thread.recorded.connect(self._audio_ready); self.audio_thread.error.connect(self._audio_error); self.audio_thread.start()
    def _audio_ready(self, data, duration, rms):
        self.is_recording = False
        self.audio_thread = None
        self._set_inline_recording_visual(False)
        if not data or duration < 0.3:
            self.status.setText("Aucun son détecté")
            return
        documents, attachments_html = self._take_current_attachments()
        self.begin_response("Question audio", attachments_html)
        self.ask_requested.emit(documents, "", data)
    def _audio_error(self, message):
        self.is_recording = False
        self.audio_thread = None
        self._set_inline_recording_visual(False)
        self.status.setText(message)

    def cleanup_temp_files(self):
        """Supprime les fichiers temporaires créés pour les aperçus et les captures de sources."""
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self._temp_files.clear()

    def closeEvent(self, event):
        self.cleanup_temp_files()
        super().closeEvent(event)

