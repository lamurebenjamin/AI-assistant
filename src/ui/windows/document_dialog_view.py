"""Construction de la vue documentaire ; le dialogue conserve les signaux et l'etat."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SmoothScrollArea

import src.ui.design_tokens as t
from src.ui.fluent_compat import install_tooltip
from src.ui.icons import create_svg_icon
from src.ui.stylesheet import (
    qss_response_scroll_area,
    qss_transparent_surface,
    qss_turn_navigation,
)
from src.ui.widgets.animated_buttons import AnimatedComposerButton
from src.ui.widgets.composer_bar import ComposerBar
from src.ui.widgets.document_attachment_preview import DocumentAttachmentPreview
from src.ui.widgets.hairline import HairlineSeparator
from src.ui.widgets.slash_command_popup import SlashCommandPopup
from src.ui.widgets.window_chrome import WindowChrome


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
