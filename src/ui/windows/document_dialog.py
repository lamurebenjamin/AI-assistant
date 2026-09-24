"""Fenêtre d'analyse et de dialogue documentaire (PDF, images, texte)."""

import html
import os
import re
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action as FluentAction,
)
from qfluentwidgets import (
    RoundMenu,
    SmoothScrollArea,
)

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        fitz = None

import src.ui.design_tokens as t
from core.skill_manager import SkillManager
from src.config.schema import LOGGER
from src.ui.fluent_compat import install_tooltip
from src.ui.icons import create_svg_icon, get_application_icon, get_default_tool_icon
from src.ui.stylesheet import (
    qss_document_dialog,
    qss_document_preview_dialog,
    qss_response_scroll_area,
    qss_transparent_surface,
    qss_turn_navigation,
)
from src.ui.theme import apply_acrylic_blur, apply_rounded_corners
from src.ui.widgets.animated_buttons import AnimatedComposerButton
from src.ui.widgets.composer_bar import ComposerBar
from src.ui.widgets.document_attachment_preview import DocumentAttachmentPreview
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.slash_command_popup import SlashCommandPopup
from src.ui.widgets.window_chrome import WindowChrome
from src.ui.windows.conversation_controller import ConversationController
from src.ui.windows.document_composer_controller import DocumentComposerController
from src.ui.windows.document_conversation_renderer import DocumentConversationRenderer
from src.ui.windows.document_response_controller import DocumentResponseController


class DocumentDialog(QDialog):
    """Fenêtre Ctrl+9 harmonisée avec les fenêtres de résultats et pensée comme un chat."""
    ask_requested = Signal(list, str, object, object)

    WINDOW_WIDTH = 480
    MIN_HEIGHT = 80
    MAX_HEIGHT = 620
    MAX_RESPONSE_HEIGHT = 440
    FONT_SIZE_OFFSET = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.host = parent
        self.apply_config(initial=True)
        if self.host is not None and hasattr(self.host, "skill_manager"):
            self.skill_manager = self.host.skill_manager
        else:
            self.skill_manager = SkillManager()
            self.skill_manager.discover()
        self._pending_forced_tool = None
        self._pending_skill_tag = None
        self._setting_skill_text = False
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
        self._prompt_history_index = None
        self._prompt_history_draft = ""
        # Références conservées pendant le streaming Ctrl+9. La bulle courante
        # est mise à jour en place au lieu de reconstruire toute la conversation.
        self.current_assistant_bubble = None
        self.current_thinking_widget = None
        self.streaming_response_active = False
        self._allow_shrink_height = False
        self.conversation_controller = ConversationController(self)
        self.response_controller = DocumentResponseController(self)
        self.composer_controller = DocumentComposerController(self)
        self.conversation_renderer = DocumentConversationRenderer(self)
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

    def apply_config(self, ctrl9_config=None, initial=False):
        """Applique la configuration CTRL+9 (largeur, hauteur max, taille police)."""
        if ctrl9_config is None:
            if self.host is not None and hasattr(self.host, "config") and isinstance(self.host.config, dict):
                ctrl9_config = self.host.config.get("ctrl9", {})
            else:
                from src.config.manager import load_config
                ctrl9_config = load_config().get("ctrl9", {})

        self.WINDOW_WIDTH = ctrl9_config.get("width", 480)
        self.MAX_HEIGHT = ctrl9_config.get("max_height", 620)
        font_size = ctrl9_config.get("font_size", 14)
        self.FONT_SIZE_OFFSET = font_size - 13
        self.MAX_RESPONSE_HEIGHT = max(180, self.MAX_HEIGHT - 180)

        self.setFixedWidth(self.WINDOW_WIDTH)
        if hasattr(self, "_attachment_preview"):
            self._attachment_preview.font_size_offset = self.FONT_SIZE_OFFSET
        if hasattr(self, "response"):
            self.response.setMaximumHeight(self.MAX_RESPONSE_HEIGHT)
        if not initial:
            self._apply_font_styles()
            if hasattr(self, "turns") and self.turns:
                self._render_conversation()
            else:
                self._update_height()

    def _apply_font_styles(self):
        self.setStyleSheet(qss_document_dialog(self.FONT_SIZE_OFFSET))
        if hasattr(self, "status"):
            self.status.setObjectName("DocStatus")
        if hasattr(self, "composer") and hasattr(self.composer, "refresh_theme"):
            self.composer.font_size_offset = self.FONT_SIZE_OFFSET
            self.composer.refresh_theme()

    def refresh_theme(self) -> None:
        self._apply_font_styles()
        if hasattr(self, "separator_container"):
            self.separator_container.refresh_theme()
        if hasattr(self, "header"):
            self.header.refresh_logo()
        if hasattr(self, "drop_zone"):
            self.drop_zone.setIcon(
                create_svg_icon(
                    '<path d="M12 5v14M5 12h14"/>',
                    t.COLOR_TEXT_PRIMARY,
                    t.ICON_STROKE_WIDTH,
                )
            )
        if hasattr(self, "mic"):
            self.mic_icon = create_svg_icon(
                '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>'
                '<path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8"/>',
                t.COLOR_TEXT_PRIMARY,
                1.7,
            )
            self.recording_icon = create_svg_icon(
                f'<circle cx="12" cy="12" r="6" fill="{t.COLOR_DANGER}" stroke="none"/>',
                t.COLOR_DANGER,
                1.0,
            )
            if not self.is_recording:
                self.mic.setIcon(self.mic_icon)
            else:
                self.mic.setIcon(self.recording_icon)
        if hasattr(self, "turns") and self.turns:
            self._render_conversation()

    def _build_ui(self):
        self._apply_font_styles()
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        self.panel = QFrame()
        self.panel.setObjectName("DocPanel")
        self.panel.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.panel)
        root = QVBoxLayout(self.panel); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        self.header = WindowChrome(
            "Assistant IA",
            self.panel,
            object_name="DocHeader",
            title_object_name="DocTitle",
        )
        self.header.mousePressEvent = self._header_press
        self.header.mouseMoveEvent = self._header_move
        self.header.mouseReleaseEvent = self._header_release
        close = AnimatedComposerButton("close", self.header)
        install_tooltip(close, "Fermer")
        close.clicked.connect(self.reject)
        self.header.add_action(close)
        root.addWidget(self.header)

        self.separator_container = HairlineSeparator(self.panel)
        self.header_separator = self.separator_container.line
        root.addWidget(self.separator_container)
        self.content_widget = QWidget()
        content = QVBoxLayout(self.content_widget)
        content.setContentsMargins(10, 8, 10, 8)
        content.setSpacing(4)

        self.drop_zone=QPushButton(self.content_widget); self.drop_zone.setObjectName("ActionIconButton")
        self.drop_zone.setIcon(create_svg_icon('<path d="M12 5v14M5 12h14"/>', t.COLOR_TEXT_PRIMARY, t.ICON_STROKE_WIDTH)); self.drop_zone.setIconSize(QSize(t.ICON_SIZE_BUTTON, t.ICON_SIZE_BUTTON)); self.drop_zone.setFixedHeight(t.COMPOSER_HEIGHT + 12)
        self.drop_zone.setToolTip("Ajouter un PDF ou une image"); self.drop_zone.setCursor(Qt.PointingHandCursor); self.drop_zone.clicked.connect(self._choose_files)
        self.drop_zone.hide()

        self._attachment_preview = DocumentAttachmentPreview(
            self.content_widget,
            font_size_offset=self.FONT_SIZE_OFFSET,
            update_height=self._update_height,
            fallback_pixmap=self._create_pdf_fallback_pixmap,
        )
        self.paths = self._attachment_preview.paths
        self.page_selections = self._attachment_preview.page_selections
        self.document_area = self._attachment_preview.document_area
        self.image_scroll = self._attachment_preview.image_scroll
        self.image_strip = self._attachment_preview.image_strip
        self.image_strip_layout = self._attachment_preview.image_strip_layout
        self.preview=QLabel(); self.filename=QLabel(); self.first_page=QLineEdit("1")
        self.last_page=QLineEdit("1"); self.page_info=QLabel()
        for legacy_widget in (self.preview,self.filename,self.first_page,self.last_page,self.page_info): legacy_widget.hide()

        # Une vraie pile de widgets remplace le tableau HTML unique. Les QFrame
        # prennent correctement en charge border-radius, contrairement aux cellules
        # de tableau du moteur HTML de QTextDocument.
        self.response=SmoothScrollArea(self.content_widget)
        self.response.setObjectName("Response")
        self.response.setWidgetResizable(True)
        self.response.setFrameShape(QFrame.NoFrame)
        self.response.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.response.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response.setStyleSheet(qss_response_scroll_area())
        # Aucun décalage interne : le bord gauche des bulles assistant est sur
        # le même axe que le bord gauche du compositeur « Message assistant IA ».
        # La barre verticale couvre exactement la hauteur de la conversation.
        self.response.setViewportMargins(0, 0, 0, 0)
        self.response_holder = QWidget(self.content_widget)
        response_holder_layout = QHBoxLayout(self.response_holder)
        response_holder_layout.setContentsMargins(0, 0, 8, 0)
        response_holder_layout.setSpacing(0)
        self.turn_navigation = QFrame(self.response_holder)
        self.turn_navigation.setObjectName("TurnNavigation")
        self.turn_navigation.setFixedWidth(16)
        self.turn_navigation.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.turn_navigation.setAttribute(Qt.WA_Hover, True)
        self.turn_navigation.setStyleSheet(qss_turn_navigation())
        self.turn_navigation_layout = QVBoxLayout(self.turn_navigation)
        self.turn_navigation_layout.setContentsMargins(0, 3, 0, 3)
        self.turn_navigation_layout.setSpacing(0)
        self.turn_navigation_layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        response_holder_layout.addWidget(self.turn_navigation, 0)
        response_holder_layout.addWidget(self.response, 1)
        self.conversation_widget=QWidget()
        self.conversation_widget.setStyleSheet(qss_transparent_surface())
        self.conversation_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        self.conversation_layout=QVBoxLayout(self.conversation_widget)
        # La conversation commence sur le même axe gauche que le compositeur.
        # La marge des messages utilisateur est gérée à droite de leur ligne.
        self.conversation_layout.setContentsMargins(0,0,0,0)
        self.conversation_layout.setSpacing(0)
        self.conversation_layout.setAlignment(Qt.AlignTop)
        self.response.setWidget(self.conversation_widget)
        self.response.setMinimumHeight(0)
        self.response.setMaximumHeight(self.MAX_RESPONSE_HEIGHT)
        self.response.hide()
        content.addWidget(self.response_holder, 1)
        self.response_holder.hide()

        self.status=QLabel("", self.content_widget)
        self.status.setObjectName("DocStatus")
        self.status.setTextFormat(Qt.PlainText)
        self.status.hide()
        content.addWidget(self.status)

        self.composer = ComposerBar(
            self.content_widget,
            font_size_offset=self.FONT_SIZE_OFFSET,
            document_area=self.document_area,
        )
        self.composer.installEventFilter(self)
        self.add_button = self.composer.add_button
        self.skill_tag = self.composer.skill_tag
        self.skill_tag_icon = self.composer.skill_tag.icon_label
        self.skill_tag_title = self.composer.skill_tag.title_label
        self.question = self.composer.question
        self._question_height = t.COMPOSER_HEIGHT
        self.audio_bars = self.composer.audio_bars
        self.mic = self.composer.mic
        self.send = self.composer.send
        self.stop_generation_button = self.composer.stop_generation_button
        self.drop_feedback = self.composer.drop_feedback
        self.add_button.clicked.connect(self._show_add_menu)
        self.mic_icon = create_svg_icon(
            '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>'
            '<path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8"/>',
            t.COLOR_TEXT_PRIMARY,
            1.7,
        )
        self.recording_icon = create_svg_icon(
            f'<circle cx="12" cy="12" r="6" fill="{t.COLOR_DANGER}" stroke="none"/>',
            t.COLOR_DANGER,
            1.0,
        )
        self.mic.clicked.connect(self._toggle_microphone)
        self.send.clicked.connect(self._ask_text)
        self.stop_generation_button.clicked.connect(self._stop_llm_generation)
        self.question.textChanged.connect(self._update_send_visibility)
        self.question.textChanged.connect(self._update_question_height)
        self.question.textChanged.connect(self._clear_skill_tag_when_erased)
        self.question.textChanged.connect(self._reset_prompt_history_navigation)
        self.question.skill_tag_removed.connect(self._clear_skill_tag)
        self.question.send_requested.connect(self._ask_text)
        self.question.history_requested.connect(self._navigate_prompt_history)
        self.question.pasted_files.connect(self._add_paths)

        # Le popup slash est un widget flottant (overlay) positionné au-dessus
        # du compositeur. Il n'est PAS dans le layout — sa visibilité n'agrandit
        # pas la fenêtre quand celle-ci a déjà atteint MAX_HEIGHT.
        self.slash_popup = SlashCommandPopup(self.panel)
        self.slash_popup.hide()
        self.question.set_slash_popup(self.slash_popup)
        self.question.slash_triggered.connect(self._on_slash_triggered)
        self.question.slash_dismissed.connect(self._on_slash_dismissed)
        self.slash_popup.action_selected.connect(self._on_slash_action_selected)
        content.addStretch(1)
        content.addWidget(self.composer)

        root.addWidget(self.content_widget,1)
        self._update_height()

    def _open_source_link(self, url):
        return self.conversation_controller.open_source_link(url)

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
        dialog.setStyleSheet(qss_document_preview_dialog())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        scroll = SmoothScrollArea(dialog)
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
        dialog.exec()

    def _answer_without_sources(self, answer):
        if not answer:
            return ""
        clean = re.split(r"(?im)^\s*#{2,3}\s*Sources\s*$", answer, maxsplit=1)[0]
        clean = re.split(r"(?im)^\s*Sources\s*:\s*$", clean, maxsplit=1)[0]
        # Certains modèles ajoutent des retours à la ligne avant ou après la
        # réponse. Ils ne doivent pas créer d'espace visuel parasite autour de
        # la bulle, sans modifier les retours à la ligne internes.
        return clean.lstrip().rstrip()

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
                    except Exception:  # noqa: BLE001
                        LOGGER.exception("Impossible de générer la vignette jointe du PDF")
                        preview_path = ""

            if is_pdf and (not preview_path or not os.path.isfile(preview_path)):
                preview_path = os.path.join(
                    tempfile.gettempdir(),
                    f"assistant_turn_attachment_fb_{os.getpid()}_{time.monotonic_ns()}_{index}.png",
                )
                fb_pix = self._create_pdf_fallback_pixmap(68, 88)
                fb_pix.save(preview_path, "PNG")
                self._temp_files.add(preview_path)

            if not preview_path or not os.path.isfile(preview_path):
                continue

            pixmap = QPixmap(preview_path)
            if pixmap.isNull():
                continue
            # Une vignette de document et sa ligne de pages ont la même hauteur
            # totale qu'une vignette d'image seule.
            total_h = t.DOCUMENT_THUMBNAIL_HEIGHT
            caption_h = 16 if is_pdf else 0
            image_h = total_h - caption_h
            shown = pixmap.scaled(t.DOCUMENT_THUMBNAIL_WIDTH, image_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
                f'text-align:center; font-size:{10 + self.FONT_SIZE_OFFSET}px; color:{t.COLOR_STATUS_SUBTLE};">'
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
        return self.conversation_renderer._clear_conversation_widgets()

    def _clear_turn_navigation(self):
        return self.conversation_renderer._clear_turn_navigation()

    def _render_conversation(self):
        return self.conversation_controller.render()

    def _render_conversation_impl(self):
        return self.conversation_renderer.render()

    def _update_turn_navigation_visibility(self):
        return self.conversation_renderer._update_turn_navigation_visibility()

    def _refresh_conversation_widths(self):
        return self.conversation_renderer._refresh_conversation_widths()

    def _scroll_to_bottom(self):
        return self.conversation_renderer._scroll_to_bottom()

    def _sync_conversation_widget_height(self):
        return self.conversation_renderer._sync_conversation_widget_height()

    def _update_response_scroll_policy(self):
        return self.conversation_renderer._update_response_scroll_policy()

    def _refresh_stream_view(self):
        return self.conversation_renderer._refresh_stream_view()

    def _update_height(self):
        return self.conversation_renderer._update_height()

    def _add_sources_html(self, answer, documents):
        return self.conversation_renderer._add_sources_html(answer, documents)

    def show_source_captures(self, answer, documents):
        return self.conversation_controller.show_source_captures(answer, documents)

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
            self.separator_container.show()
            self.content_widget.show()
            expanding = True
        else:
            self.expanded_height = max(self.MIN_HEIGHT, current)
            self.separator_container.hide()
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
        if not self.isVisible():
            return
        if self.is_collapsed:
            self.toggle_collapse()
        self.raise_()
        self.activateWindow()
        self.question.setFocus(Qt.ActiveWindowFocusReason)
        cursor = self.question.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.question.setTextCursor(cursor)
        self.question.ensurePolished()

    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self._apply_effects)
        QTimer.singleShot(0,self._update_height)
        # Windows peut appliquer l'activation après show(). Réessayer après les
        # étapes d'activation garantit que la première frappe arrive au champ.
        for delay in (0, 80, 180):
            QTimer.singleShot(delay, self.focus_message_input)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_rounded_masks()

    def _update_rounded_masks(self):
        radius = max(1, int(t.RADIUS_2XL.rstrip("px")))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        if hasattr(self, "panel"):
            panel_path = QPainterPath()
            panel_path.addRoundedRect(QRectF(self.panel.rect()), radius, radius)
            self.panel.setMask(QRegion(panel_path.toFillPolygon().toPolygon()))

    def _apply_effects(self):
        # Applique le flou DWM après la création du HWND. Un seul arrondi est
        # dessiné par Qt sur DocPanel : l'arrondi DWM natif est volontairement
        # désactivé pour éviter un second rayon différent.
        if self.windowHandle() is None:
            return
        self._update_rounded_masks()
        apply_acrylic_blur(int(self.winId()))
        apply_rounded_corners(int(self.winId()))

    def _update_question_height(self):
        return self.composer_controller._update_question_height()

    def _update_send_visibility(self):
        return self.composer_controller._update_send_visibility()

    def _stop_llm_generation(self):
        return self.composer_controller._stop_llm_generation()

    def _ask_text(self):
        return self.composer_controller._ask_text()

    def _prompt_history(self):
        return self.composer_controller._prompt_history()

    def _reset_prompt_history_navigation(self):
        return self.composer_controller._reset_prompt_history_navigation()

    def _navigate_prompt_history(self, direction: int):
        return self.composer_controller._navigate_prompt_history(direction)

    def _set_inline_recording_visual(self, active):
        return self.composer_controller._set_inline_recording_visual(active)

    def _toggle_microphone(self):
        return self.composer_controller._toggle_microphone()

    def _audio_ready(self, data, duration, rms):
        return self.composer_controller._audio_ready(data, duration, rms)

    def _audio_error(self, message):
        return self.composer_controller._audio_error(message)

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
    def _create_add_menu(self) -> RoundMenu:
        menu = RoundMenu(parent=self)
        menu.setObjectName("ComposerAddMenu")

        # 1. Option Ajouter un PDF ou une image
        act_add_file = FluentAction("Ajouter un PDF ou une image")
        act_add_file.triggered.connect(self._choose_files)
        menu.addAction(act_add_file)

        # 2. Séparateur
        menu.addSeparator()

        # 3. Liste des skills découverts avec sous-menus
        skill_mgr = getattr(self, "skill_manager", None)
        if skill_mgr is None and self.host is not None:
            skill_mgr = getattr(self.host, "skill_manager", None)
        if skill_mgr is None:
            skill_mgr = SkillManager()
            skill_mgr.discover()
            self.skill_manager = skill_mgr

        discovered_skills = sorted(skill_mgr.skills.keys()) if skill_mgr.skills else skill_mgr.list_skills()
        if not discovered_skills:
            discovered_skills = skill_mgr.discover()

        skill_titles = {
            "pdf": "Document PDF (.pdf)",
            "docx": "Document Word (.docx)",
            "excel": "Classeur Excel (.xlsx)",
            "pptx": "Présentation PowerPoint (.pptx)",
        }
        tool_titles = {
            "create_pdf": "Créer un document PDF",
            "create_docx": "Créer un document Word",
            "create_excel": "Créer un classeur Excel",
            "create_pptx": "Créer une présentation PowerPoint",
            "Liste": "Liste des FTNC",
            "Details": "Détails d'une FTNC",
            "Détails": "Détails d'une FTNC",
        }

        for skill_name in discovered_skills:
            skill_display = skill_titles.get(skill_name, f"Skill {skill_name.capitalize()}")
            sub_menu = RoundMenu(skill_display, parent=menu)
            sub_menu.setObjectName("ComposerAddMenu")

            skill_tools = [
                t for t in skill_mgr.tools.values()
                if t.get("skill") == skill_name
            ]
            if not skill_tools:
                act_none = FluentAction("Aucune action disponible")
                act_none.setEnabled(False)
                sub_menu.addAction(act_none)
            else:
                for tool in skill_tools:
                    t_name = tool.get("name", "")
                    t_desc = tool.get("description", "")
                    t_title = tool_titles.get(t_name, t_name.replace("_", " ").capitalize())
                    act_tool = FluentAction(t_title)
                    if t_desc:
                        act_tool.setToolTip(t_desc)
                    act_tool.triggered.connect(
                        lambda checked=False, s=skill_name, t=t_name: self._on_skill_tool_selected(s, t)
                    )
                    sub_menu.addAction(act_tool)

            menu.addMenu(sub_menu)

        return menu

    def _show_add_menu(self):
        menu = self._create_add_menu()
        btn_pos = self.add_button.mapToGlobal(QPoint(0, 0))
        menu_size = menu.sizeHint()
        target_y = btn_pos.y() - menu_size.height() - 4
        screen = QApplication.screenAt(btn_pos) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            if target_y < avail.top():
                target_y = btn_pos.y() + self.add_button.height() + 4
        menu.exec(QPoint(btn_pos.x(), target_y))

    def _on_skill_tool_selected(self, skill_name: str, tool_name: str):
        self._select_skill_tool(skill_name, tool_name)

    def _skill_tool_details(self, skill_name, tool_name):
        skill_manager = self.skill_manager
        info = skill_manager.get_tool(tool_name)
        skill = skill_manager.get_skill(skill_name)
        skill_title = str(getattr(skill, "name", skill_name)).strip() or skill_name
        tool_title = tool_name.replace("_", " ").capitalize()
        if tool_name in {"create_pdf", "create_docx", "create_excel", "create_pptx"}:
            tool_title = {
                "create_pdf": "Créer un document PDF",
                "create_docx": "Créer un document Word",
                "create_excel": "Créer un classeur Excel",
                "create_pptx": "Créer une présentation PowerPoint",
            }[tool_name]
        parameters = info.get("parameters") or {}
        required = parameters.get("required") or []
        icon_path = skill_manager.get_skill_icon(skill_name)
        return {
            "skill_name": skill_name,
            "tool_name": tool_name,
            "title": f"{skill_title} - {tool_title}",
            "icon": icon_path,
            "requires_arguments": bool(required),
        }

    def _set_skill_tag(self, tag):
        self._pending_skill_tag = tag
        icon_path = tag.get("icon")
        icon_html = ""
        if icon_path:
            icon_html = (
                f'<img src="{Path(icon_path).as_uri()}" width="18" height="18" '
                'style="vertical-align:middle;">&nbsp;'
            )
        tag_html = (
            f'<span style="background-color:{t.COLOR_PRIMARY_LIGHT}; '
            f'color:{t.COLOR_TEXT_PRIMARY}; font-weight:600; '
            f'padding:0 5px 1px; vertical-align:middle;">{icon_html}'
            f'{html.escape(tag["title"])}</span>&nbsp;'
        )
        self._setting_skill_text = True
        cursor = self.question.textCursor()
        cursor.movePosition(QTextCursor.Start)
        previous_text = self.question.toPlainText()
        cursor.insertHtml(tag_html)
        self.question.setTextCursor(cursor)
        inserted_length = max(1, len(self.question.toPlainText()) - len(previous_text))
        self.question.set_skill_tag_range(0, inserted_length)
        self._setting_skill_text = False
        self.skill_tag.hide()

    def _clear_skill_tag_when_erased(self):
        if (
            not self._setting_skill_text
            and self._pending_skill_tag
            and not self.question.toPlainText().replace("\uFFFC", "").strip()
        ):
            self._pending_forced_tool = None
            self._clear_skill_tag()

    def _clear_skill_tag(self):
        title = str((self._pending_skill_tag or {}).get("title", ""))
        if title:
            self._setting_skill_text = True
            self.question.remove_skill_tag()
            self._setting_skill_text = False
        self._pending_skill_tag = None
        self.skill_tag.hide()

    def _select_skill_tool(self, skill_name, tool_name, existing_text=""):
        tag = self._skill_tool_details(skill_name, tool_name)
        self._setting_skill_text = True
        self.question.setPlainText(existing_text)
        self._setting_skill_text = False
        self._set_skill_tag(tag)
        self._pending_forced_tool = tool_name
        self.question.setFocus()
        if tag["requires_arguments"]:
            self._update_send_visibility()
            self._update_question_height()

    # ------------------------------------------------------------------
    # Slash-command popup handlers
    # ------------------------------------------------------------------
    def _build_slash_actions(self):
        """Construit la liste d'actions à partir des skills découverts."""
        skill_mgr = getattr(self, "skill_manager", None)
        if skill_mgr is None and self.host is not None:
            skill_mgr = getattr(self.host, "skill_manager", None)
        if skill_mgr is None:
            skill_mgr = SkillManager()
            skill_mgr.discover()
            self.skill_manager = skill_mgr

        skill_titles = {
            "pdf": "Document PDF",
            "docx": "Document Word",
            "excel": "Classeur Excel",
            "pptx": "Présentation PowerPoint",
            "ftnc": "FTNC",
        }
        tool_titles = {
            "create_pdf": "Créer un document PDF",
            "create_docx": "Créer un document Word",
            "create_excel": "Créer un classeur Excel",
            "create_pptx": "Créer une présentation PowerPoint",
        }
        actions = []
        discovered = sorted(skill_mgr.skills.keys()) if skill_mgr.skills else skill_mgr.list_skills()
        if not discovered:
            discovered = skill_mgr.discover()

        for skill_name in discovered:
            skill_tools = [
                t for t in skill_mgr.tools.values()
                if t.get("skill") == skill_name
            ]
            for tool in skill_tools:
                t_name = tool.get("name", "")
                t_desc = tool.get("description", "")
                t_title = tool_titles.get(t_name, t_name.replace("_", " ").capitalize())
                skill_icon = skill_mgr.get_skill_icon(skill_name)
                icon = (
                    get_application_icon(skill_icon)
                    if skill_icon
                    else get_default_tool_icon()
                )
                actions.append({
                    "command": f"/{t_name}",
                    "title": t_title,
                    "description": t_desc,
                    "skill": skill_titles.get(skill_name, skill_name.capitalize()),
                    "icon": icon,
                    "tool_name": t_name,
                    "skill_name": skill_name,
                })
        return actions

    def _position_slash_popup(self):
        """Positionne le popup slash comme overlay flottant au-dessus du compositeur."""
        if not hasattr(self, 'composer') or not hasattr(self, 'panel') or not hasattr(self, 'slash_popup'):
            return
        # La hauteur du popup s'adapte exactement à son contenu (pas de marge vide)
        popup_h = self.slash_popup.content_height() if hasattr(self.slash_popup, 'content_height') else self.slash_popup.height()
        popup_w = self.composer.width()
        # Obtenir la position du compositeur par rapport au panel
        composer_pos = self.composer.mapTo(self.panel, self.composer.rect().topLeft())
        # Positionner juste au-dessus du compositeur
        x = composer_pos.x()
        y = composer_pos.y() - popup_h - 6
        y = max(38, y)  # ne pas sortir au-dessus du header
        self.slash_popup.setFixedWidth(popup_w)
        self.slash_popup.setFixedHeight(popup_h)
        self.slash_popup.move(x, y)
        self.slash_popup.raise_()

    def _on_slash_triggered(self, query: str, slash_pos: int):
        """Appelé quand l'utilisateur tape '/' dans le champ de saisie."""
        if not self.slash_popup.all_actions:
            self.slash_popup.set_actions(self._build_slash_actions())

        has_results = self.slash_popup.filter_actions(query)
        if has_results or not query:
            self.slash_popup.show()
            self._update_height()
            self._position_slash_popup()
            self.slash_popup.raise_()
        else:
            self._on_slash_dismissed()

    def _on_slash_dismissed(self):
        """Masque le popup overlay et restaure la hauteur de la fenêtre."""
        if self.slash_popup.isVisible():
            self.slash_popup.hide()
            self._update_height()

    def _on_slash_action_selected(self, action: dict):
        """Appelé quand l'utilisateur sélectionne une action du menu slash."""
        tool_name = action.get("tool_name", "")
        skill_name = action.get("skill_name", "")

        # Remplacer le texte "/commande" par le prompt de la skill
        full_text = self.question.toPlainText()
        import re as _re
        cleaned = _re.sub(r'(?:^|\s)/\S*$', '', full_text).strip()

        self._select_skill_tool(skill_name, tool_name, cleaned)
        self._on_slash_dismissed()

    def _choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Ajouter des documents","","Documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        self._add_paths(paths)

    @staticmethod
    def _create_pdf_fallback_pixmap(width: int, height: int) -> QPixmap:
        """Crée une vignette neutre lorsque le rendu PDF n'est pas disponible."""
        pixmap = QPixmap(max(1, int(width)), max(1, int(height)))
        pixmap.fill(QColor(t.COLOR_PREVIEW_BACKGROUND))
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(t.COLOR_BORDER), 1))
        painter.drawRect(pixmap.rect().adjusted(1, 1, -2, -2))
        painter.setPen(QColor(t.COLOR_TEXT_SECONDARY))
        painter.setFont(QFont("Arial", max(8, min(14, int(width / 7)))))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "PDF")
        painter.end()
        return pixmap

    def _page_count(self,path):
        return self._attachment_preview.page_count(path)

    def _add_paths(self, paths):
        self._attachment_preview.add_paths(paths, self._supported)

    def _clear_image_strip(self):
        self._attachment_preview.clear_image_strip()

    def _remove_path(self, path):
        self._attachment_preview.remove_path(path)

    def _rebuild_image_strip(self):
        self._attachment_preview.rebuild_image_strip()

    def _show_document(self, index=-1):
        if not self.paths:
            self._attachment_preview.show_document(index)
            self.status.hide()
            return
        self._attachment_preview.show_document(index)
        self.status.setText("Pi?ces jointes pr?tes")
        self._update_height()

    def _save_page_range(self):
        return

    def _remove_current(self):
        self._attachment_preview.remove_current()

    def _specs(self):
        return [{"path":p,"pages":list(range(self.page_selections[p][0],self.page_selections[p][1]+1))} for p in self.paths]

    def begin_response(self, question, attachments_html="", skill_tag=None, documents=None):
        return self.response_controller.begin_response(
            question, attachments_html, skill_tag, documents
        )

    def append_thinking(self, text):
        return self.response_controller.append_thinking(text)

    def append_response(self, text):
        return self.response_controller.append_response(text)

    def _flush_stream_render(self):
        return self.response_controller._flush_stream_render()

    def _on_tool_widget_toggled(self):
        return self.response_controller._on_tool_widget_toggled()

    def _finish_toggle_layout(self, scroll_bar, previous_value):
        return self.response_controller._finish_toggle_layout(
            scroll_bar, previous_value
        )

    def record_tool_event(self, phase: str, name: str, detail: str):
        return self.response_controller.record_tool_event(phase, name, detail)

    def finish_response(self):
        return self.response_controller.finish_response()

    def show_error(self, message):
        return self.response_controller.show_error(message)

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
        thread = self.host.document_thread if self.host is not None else None
        if thread is not None and thread.isRunning():
            thread.stop()
        self._stop_llm_generation()
        if self.audio_thread is not None and self.audio_thread.isRunning():
            self.audio_thread.stop_recording()
        self.cleanup_temp_files()
        super().closeEvent(event)
