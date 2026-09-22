"""Construction of the settings dialog tabs."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.schema import DEFAULT_CONFIG
import src.ui.design_tokens as t
from src.ui.stylesheet import qss_settings_emphasis


@dataclass
class SettingsTabs:
    widget: QTabWidget
    llm_layout: QVBoxLayout
    voice_layout: QVBoxLayout
    shortcuts_layout: QVBoxLayout


class SettingsTabsBuilder:
    """Build the settings tabs and expose the dialog-owned controls."""

    def __init__(self, dialog):
        self.dialog = dialog

    def build(self) -> SettingsTabs:
        dialog = self.dialog
        tabs = QTabWidget(dialog.content_widget)
        tabs.setDocumentMode(True)

        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        llm_layout.setContentsMargins(10, 12, 10, 10)
        llm_layout.setSpacing(12)

        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        voice_layout.setContentsMargins(10, 12, 10, 10)
        voice_layout.setSpacing(12)

        shortcuts_tab = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_tab)
        shortcuts_layout.setContentsMargins(10, 12, 10, 10)
        shortcuts_layout.setSpacing(12)

        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setContentsMargins(16, 16, 16, 16)
        appearance_layout.setSpacing(16)

        theme_box = QGroupBox("Thème de l'application", appearance_tab)
        theme_box_layout = QVBoxLayout(theme_box)
        theme_box_layout.setContentsMargins(14, 14, 14, 14)
        theme_box_layout.setSpacing(10)

        theme_row = QHBoxLayout()
        theme_lbl = QLabel("Mode d'affichage :", theme_box)
        theme_lbl.setStyleSheet(qss_settings_emphasis())
        dialog.theme_combo = QComboBox(theme_box)
        dialog.theme_combo.addItem("🌙 Sombre (Antigravity)", "dark")
        dialog.theme_combo.addItem("☀️ Clair", "light")
        current_t = dialog.config.get("theme", "dark")
        dialog.theme_combo.setCurrentIndex(0 if current_t == "dark" else 1)
        dialog.theme_combo.currentIndexChanged.connect(dialog._on_theme_preview_changed)
        theme_row.addWidget(theme_lbl)
        theme_row.addWidget(dialog.theme_combo, 1)
        theme_box_layout.addLayout(theme_row)

        theme_desc = QLabel(
            "Le mode sombre reproduit la charte Antigravity : fond page, surfaces "
            "et accents bleus, icônes claires.",
            theme_box,
        )
        theme_desc.setObjectName("SettingsHint")
        theme_desc.setWordWrap(True)
        theme_box_layout.addWidget(theme_desc)

        appearance_layout.addWidget(theme_box)
        appearance_layout.addStretch(1)

        ctrl9_tab = QWidget()
        ctrl9_layout = QVBoxLayout(ctrl9_tab)
        ctrl9_layout.setContentsMargins(16, 16, 16, 16)
        ctrl9_layout.setSpacing(14)
        ctrl9_cfg = dialog.config.get("ctrl9", DEFAULT_CONFIG.get("ctrl9", {}))

        dim_box = QGroupBox("Dimensions de la fenêtre", ctrl9_tab)
        dim_layout = QVBoxLayout(dim_box)
        dim_layout.setContentsMargins(14, 14, 14, 14)
        dim_layout.setSpacing(10)

        width_row = QHBoxLayout()
        width_lbl = QLabel("Largeur standard :", dim_box)
        width_lbl.setStyleSheet(qss_settings_emphasis())
        dialog.ctrl9_width_spin = QSpinBox(dim_box)
        dialog.ctrl9_width_spin.setRange(360, 1000)
        dialog.ctrl9_width_spin.setSingleStep(10)
        dialog.ctrl9_width_spin.setSuffix(" px")
        dialog.ctrl9_width_spin.setValue(int(ctrl9_cfg.get("width", 480)))
        dialog.ctrl9_width_spin.setFixedWidth(110)
        width_row.addWidget(width_lbl)
        width_row.addStretch(1)
        width_row.addWidget(dialog.ctrl9_width_spin)
        dim_layout.addLayout(width_row)

        width_desc = QLabel("Largeur par défaut de la fenêtre lors de l'ouverture (défaut : 480 px, min : 360 px, max : 1000 px).", dim_box)
        width_desc.setObjectName("SettingsHint")
        width_desc.setWordWrap(True)
        dim_layout.addWidget(width_desc)

        height_row = QHBoxLayout()
        height_lbl = QLabel("Hauteur maximale :", dim_box)
        height_lbl.setStyleSheet(qss_settings_emphasis())
        dialog.ctrl9_max_height_spin = QSpinBox(dim_box)
        dialog.ctrl9_max_height_spin.setRange(350, 1200)
        dialog.ctrl9_max_height_spin.setSingleStep(10)
        dialog.ctrl9_max_height_spin.setSuffix(" px")
        dialog.ctrl9_max_height_spin.setValue(int(ctrl9_cfg.get("max_height", 620)))
        dialog.ctrl9_max_height_spin.setFixedWidth(110)
        height_row.addWidget(height_lbl)
        height_row.addStretch(1)
        height_row.addWidget(dialog.ctrl9_max_height_spin)
        dim_layout.addLayout(height_row)

        height_desc = QLabel("Hauteur maximale de la fenêtre lorsque le contenu se développe (défaut : 620 px, min : 350 px, max : 1200 px).", dim_box)
        height_desc.setObjectName("SettingsHint")
        height_desc.setWordWrap(True)
        dim_layout.addWidget(height_desc)
        ctrl9_layout.addWidget(dim_box)

        font_box = QGroupBox("Taille de la police du texte", ctrl9_tab)
        font_layout = QVBoxLayout(font_box)
        font_layout.setContentsMargins(14, 14, 14, 14)
        font_layout.setSpacing(10)
        font_row = QHBoxLayout()
        font_lbl = QLabel("Taille de police affichée :", font_box)
        font_lbl.setStyleSheet(qss_settings_emphasis())

        dialog.ctrl9_font_btn_minus = QPushButton("−", font_box)
        dialog.ctrl9_font_btn_minus.setFixedSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
        dialog.ctrl9_font_btn_minus.setStyleSheet(qss_settings_emphasis(14, bold=True))
        dialog.ctrl9_font_size_spin = QSpinBox(font_box)
        dialog.ctrl9_font_size_spin.setRange(10, 22)
        dialog.ctrl9_font_size_spin.setSingleStep(1)
        dialog.ctrl9_font_size_spin.setSuffix(" px")
        dialog.ctrl9_font_size_spin.setValue(int(ctrl9_cfg.get("font_size", 14)))
        dialog.ctrl9_font_size_spin.setFixedWidth(80)
        dialog.ctrl9_font_size_spin.setAlignment(Qt.AlignCenter)
        dialog.ctrl9_font_btn_plus = QPushButton("+", font_box)
        dialog.ctrl9_font_btn_plus.setFixedSize(t.BUTTON_SIZE_HEADER, t.BUTTON_SIZE_HEADER)
        dialog.ctrl9_font_btn_plus.setStyleSheet(qss_settings_emphasis(14, bold=True))

        dialog.ctrl9_font_btn_minus.clicked.connect(
            lambda: dialog.ctrl9_font_size_spin.setValue(dialog.ctrl9_font_size_spin.value() - 1)
        )
        dialog.ctrl9_font_btn_plus.clicked.connect(
            lambda: dialog.ctrl9_font_size_spin.setValue(dialog.ctrl9_font_size_spin.value() + 1)
        )
        font_row.addWidget(font_lbl)
        font_row.addStretch(1)
        font_row.addWidget(dialog.ctrl9_font_btn_minus)
        font_row.addWidget(dialog.ctrl9_font_size_spin)
        font_row.addWidget(dialog.ctrl9_font_btn_plus)
        font_layout.addLayout(font_row)

        font_desc = QLabel("Taille de police appliquée aux messages, au bloc de raisonnement et au compositeur (défaut : 14 px).", font_box)
        font_desc.setObjectName("SettingsHint")
        font_desc.setWordWrap(True)
        font_layout.addWidget(font_desc)

        dialog.ctrl9_preview_label = QLabel("Aperçu : L'assistant IA analyse les documents et affiche son raisonnement.", font_box)
        dialog.ctrl9_preview_label.setWordWrap(True)
        dialog._refresh_ctrl9_preview(dialog.ctrl9_font_size_spin.value())
        dialog.ctrl9_font_size_spin.valueChanged.connect(dialog._refresh_ctrl9_preview)
        font_layout.addWidget(dialog.ctrl9_preview_label)
        ctrl9_layout.addWidget(font_box)
        ctrl9_layout.addStretch(1)

        tabs.addTab(llm_tab, "LLM")
        tabs.addTab(voice_tab, "Assistant vocal")
        tabs.addTab(shortcuts_tab, "Raccourcis")
        tabs.addTab(ctrl9_tab, "Fenêtre CTRL+9")
        tabs.addTab(appearance_tab, "Apparence")
        return SettingsTabs(tabs, llm_layout, voice_layout, shortcuts_layout)
