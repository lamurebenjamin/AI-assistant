"""Blocs QSS partagés entre toutes les fenêtres de l'application.

Chaque fonction retourne une chaîne QSS prête à être concaténée dans
un appel ``setStyleSheet()``. Utilise dynamiquement les tokens de
``src.ui.design_tokens`` selon le thème actif.

Ce module est un point de réexportation : les consommateurs importent
depuis ``src.ui.stylesheet`` quelle que soit la provenance réelle des blocs.
"""

from src.ui.stylesheet_assistant import (  # noqa: F401
    qss_assistant_body,
    qss_voice_recording_indicator,
)
from src.ui.stylesheet_base import (  # noqa: F401
    qss_acrylic_panel,
    qss_buttons,
    qss_hairline,
    qss_header_icon_button,
    qss_inputs,
    qss_list_widget,
    qss_menu,
    qss_opaque_panel,
    qss_scrollbar,
    qss_scrollbar_hidden_horizontal,
    qss_tab_widget,
    qss_title_label,
    qss_tool_button,
    qss_tooltip,
    qss_transparent_surface,
)
from src.ui.stylesheet_builders import (  # noqa: F401
    build_acrylic_window_qss,
    build_document_dialog_qss,
    build_settings_qss,
)
from src.ui.stylesheet_conversation import (  # noqa: F401
    qss_document_attachment_scroll,
    qss_response_scroll_area,
    qss_slash_command_label,
    qss_slash_description,
    qss_slash_header,
    qss_slash_icon_label,
    qss_slash_popup,
    qss_turn_navigation,
)
from src.ui.stylesheet_document import (
    qss_ctrl9_preview,
    qss_document_dialog,
    qss_document_page_dash,
    qss_document_page_editor,
    qss_document_page_name,
    qss_document_preview_dialog,
    qss_tool_call_step,
    qss_tool_code_browser,
)
from src.ui.stylesheet_settings import (  # noqa: F401
    qss_runtime_values,
    qss_settings_emphasis,
    qss_settings_local,
)
from src.ui.stylesheet_tools import (  # noqa: F401
    qss_shimmer_status_label,
    qss_skill_tag_frame,
    qss_skill_tag_title,
    qss_status_label,
    qss_thinking_details,
    qss_timeline_connector,
    qss_timeline_header_title,
    qss_tool_group_header,
    qss_tool_steps_container,
)

__all__ = [
    "qss_ctrl9_preview",
    "qss_document_dialog",
    "qss_document_page_dash",
    "qss_document_page_editor",
    "qss_document_page_name",
    "qss_document_preview_dialog",
    "qss_tool_call_step",
    "qss_tool_code_browser",
]
