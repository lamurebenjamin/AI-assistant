"""Construction of the settings dialog tabs."""

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# QFluentWidgets : widgets natifs Windows 11
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    Pivot,
    PushButton,
    SpinBox,
)

import src.ui.design_tokens as t
from src.config.schema import DEFAULT_CONFIG
from src.ui.stylesheet import qss_settings_emphasis

# Alias pour compatibilité avec le code existant
QComboBox = ComboBox
QSpinBox = SpinBox
QPushButton = PushButton
QLabel = BodyLabel


@dataclass
class SettingsTabs:
    widget: Pivot
    stack: QStackedWidget
    llm_layout: QVBoxLayout
    voice_layout: QVBoxLayout
    shortcuts_layout: QVBoxLayout
    appearance_tab: QWidget
    ctrl9_tab: QWidget


class AppearanceTab(QWidget):
    """Page autonome de sélection du thème de l'application."""

    def __init__(self, config: dict, on_theme_changed, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        theme_box = QGroupBox("Thème de l'application", self)
        theme_box_layout = QVBoxLayout(theme_box)
        theme_box_layout.setContentsMargins(14, 14, 14, 14)
        theme_box_layout.setSpacing(10)

        theme_row = QHBoxLayout()
        theme_lbl = QLabel("Mode d'affichage :", theme_box)
        theme_lbl.setStyleSheet(qss_settings_emphasis())
        self.theme_combo = QComboBox(theme_box)
        self.theme_combo.addItem("🌙 Sombre (Antigravity)", "dark")
        self.theme_combo.addItem("☀️ Clair", "light")
        current_theme = config.get("theme", "dark")
        self.theme_combo.setCurrentIndex(0 if current_theme == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(on_theme_changed)
        theme_row.addWidget(theme_lbl)
        theme_row.addWidget(self.theme_combo, 1)
        theme_box_layout.addLayout(theme_row)

        theme_desc = QLabel(
            "Le mode sombre reproduit la charte Antigravity : fond page, surfaces "
            "et accents bleus, icônes claires.",
            theme_box,
        )
        theme_desc.setObjectName("SettingsHint")
        theme_desc.setWordWrap(True)
        theme_box_layout.addWidget(theme_desc)
        layout.addWidget(theme_box)
        layout.addStretch(1)


class Ctrl9Tab(QWidget):
    """Page autonome de configuration de la fenêtre Ctrl+9."""

    def __init__(self, config: dict, on_preview_changed, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        ctrl9_config = config.get("ctrl9", DEFAULT_CONFIG.get("ctrl9", {}))

        dim_box = QGroupBox("Dimensions de la fenêtre", self)
        dim_layout = QVBoxLayout(dim_box)
        dim_layout.setContentsMargins(14, 14, 14, 14)
        dim_layout.setSpacing(10)

        width_row = QHBoxLayout()
        width_lbl = QLabel("Largeur standard :", dim_box)
        width_lbl.setStyleSheet(qss_settings_emphasis())
        self.width_spin = QSpinBox(dim_box)
        self.width_spin.setRange(360, 1000)
        self.width_spin.setSingleStep(10)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(int(ctrl9_config.get("width", 480)))
        self.width_spin.setFixedWidth(110)
        width_row.addWidget(width_lbl)
        width_row.addStretch(1)
        width_row.addWidget(self.width_spin)
        dim_layout.addLayout(width_row)

        width_desc = QLabel(
            "Largeur par défaut de la fenêtre lors de l'ouverture "
            "(défaut : 480 px, min : 360 px, max : 1000 px).",
            dim_box,
        )
        width_desc.setObjectName("SettingsHint")
        width_desc.setWordWrap(True)
        dim_layout.addWidget(width_desc)

        height_row = QHBoxLayout()
        height_lbl = QLabel("Hauteur maximale :", dim_box)
        height_lbl.setStyleSheet(qss_settings_emphasis())
        self.max_height_spin = QSpinBox(dim_box)
        self.max_height_spin.setRange(350, 1200)
        self.max_height_spin.setSingleStep(10)
        self.max_height_spin.setSuffix(" px")
        self.max_height_spin.setValue(int(ctrl9_config.get("max_height", 620)))
        self.max_height_spin.setFixedWidth(110)
        height_row.addWidget(height_lbl)
        height_row.addStretch(1)
        height_row.addWidget(self.max_height_spin)
        dim_layout.addLayout(height_row)

        height_desc = QLabel(
            "Hauteur maximale de la fenêtre lorsque le contenu se développe "
            "(défaut : 620 px, min : 350 px, max : 1200 px).",
            dim_box,
        )
        height_desc.setObjectName("SettingsHint")
        height_desc.setWordWrap(True)
        dim_layout.addWidget(height_desc)
        layout.addWidget(dim_box)

        font_box = QGroupBox("Taille de la police du texte", self)
        font_layout = QVBoxLayout(font_box)
        font_layout.setContentsMargins(14, 14, 14, 14)
        font_layout.setSpacing(10)
        font_row = QHBoxLayout()
        font_lbl = QLabel("Taille de police affichée :", font_box)
        font_lbl.setStyleSheet(qss_settings_emphasis())
        self.font_btn_minus = QPushButton("−", font_box)
        self.font_btn_minus.setFixedSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
        self.font_size_spin = QSpinBox(font_box)
        self.font_size_spin.setRange(10, 22)
        self.font_size_spin.setSingleStep(1)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setValue(int(ctrl9_config.get("font_size", 14)))
        self.font_size_spin.setFixedWidth(80)
        self.font_btn_plus = QPushButton("+", font_box)
        self.font_btn_plus.setFixedSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
        self.font_btn_minus.clicked.connect(
            lambda: self.font_size_spin.setValue(self.font_size_spin.value() - 1)
        )
        self.font_btn_plus.clicked.connect(
            lambda: self.font_size_spin.setValue(self.font_size_spin.value() + 1)
        )
        font_row.addWidget(font_lbl)
        font_row.addStretch(1)
        font_row.addWidget(self.font_btn_minus)
        font_row.addWidget(self.font_size_spin)
        font_row.addWidget(self.font_btn_plus)
        font_layout.addLayout(font_row)

        font_desc = QLabel(
            "Taille de police appliquée aux messages, au bloc de raisonnement "
            "et au compositeur (défaut : 14 px).",
            font_box,
        )
        font_desc.setObjectName("SettingsHint")
        font_desc.setWordWrap(True)
        font_layout.addWidget(font_desc)
        self.preview_label = QLabel(
            "Aperçu : L'assistant IA analyse les documents et affiche son raisonnement.",
            font_box,
        )
        self.preview_label.setWordWrap(True)
        self.font_size_spin.valueChanged.connect(on_preview_changed)
        font_layout.addWidget(self.preview_label)
        layout.addWidget(font_box)
        layout.addStretch(1)


class SettingsTabsBuilder:
    """Build the settings tabs and expose the dialog-owned controls."""

    def __init__(self, dialog):
        self.dialog = dialog

    def build(self) -> SettingsTabs:
        dialog = self.dialog

        # ── Pivot (navigation Fluent Windows 11) + pile de pages native ────
        pivot = Pivot(dialog.content_widget)
        stack = QStackedWidget(dialog.content_widget)

        pages: dict[str, QWidget] = {}

        def add_tab(page_id: str, label: str, page_widget: QWidget) -> None:
            """Ajoute une page au pivot et à la pile de pages."""
            stack.addWidget(page_widget)
            pages[page_id] = page_widget
            pivot.addItem(
                routeKey=page_id,
                text=label,
                onClick=lambda checked=False, pw=page_widget: stack.setCurrentWidget(pw),
            )

        pivot.currentItemChanged.connect(
            lambda route_key: stack.setCurrentWidget(pages[route_key]) if route_key in pages else None
        )

        # ── Page LLM ─────────────────────────────────────────────────────────
        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        llm_layout.setContentsMargins(10, 12, 10, 10)
        llm_layout.setSpacing(12)

        # ── Page Voix ────────────────────────────────────────────────────────
        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        voice_layout.setContentsMargins(10, 12, 10, 10)
        voice_layout.setSpacing(12)

        # ── Page Raccourcis ──────────────────────────────────────────────────
        shortcuts_tab = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_tab)
        shortcuts_layout.setContentsMargins(10, 12, 10, 10)
        shortcuts_layout.setSpacing(12)

        appearance_page = AppearanceTab(
            dialog.config,
            dialog._on_theme_preview_changed,
            dialog.content_widget,
        )
        ctrl9_page = Ctrl9Tab(
            dialog.config,
            dialog._refresh_ctrl9_preview,
            dialog.content_widget,
        )
        dialog.theme_combo = appearance_page.theme_combo
        dialog.ctrl9_width_spin = ctrl9_page.width_spin
        dialog.ctrl9_max_height_spin = ctrl9_page.max_height_spin
        dialog.ctrl9_font_btn_minus = ctrl9_page.font_btn_minus
        dialog.ctrl9_font_size_spin = ctrl9_page.font_size_spin
        dialog.ctrl9_font_btn_plus = ctrl9_page.font_btn_plus
        dialog.ctrl9_preview_label = ctrl9_page.preview_label
        dialog._refresh_ctrl9_preview(ctrl9_page.font_size_spin.value())

        # ── Ajout des pages au Pivot dans l'ordre ────────────────────────────
        add_tab("llm", "LLM", llm_tab)
        add_tab("voice", "Assistant vocal", voice_tab)
        add_tab("shortcuts", "Raccourcis", shortcuts_tab)
        add_tab("ctrl9", "Fenêtre CTRL+9", ctrl9_page)
        add_tab("appearance", "Apparence", appearance_page)

        # Sélectionner le premier onglet par défaut
        pivot.setCurrentItem("llm")
        stack.setCurrentWidget(llm_tab)

        return SettingsTabs(
            pivot,
            stack,
            llm_layout,
            voice_layout,
            shortcuts_layout,
            appearance_page,
            ctrl9_page,
        )
