import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.rendering.markdown import markdown_to_html
from src.ui import design_tokens as tokens
from src.ui.stylesheet import build_settings_qss, qss_menu, qss_tooltip

HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
FIXED_DIMENSION_LITERAL_RE = re.compile(r"setFixed(?:Width|Height)\(\s*\d+\s*\)")
UI_ROOT = Path(__file__).resolve().parents[1] / "src" / "ui"
TOKEN_FILE = UI_ROOT / "design_tokens.py"
STYLE_EXCEPTIONS = Path(__file__).resolve().parents[1] / "UI_STYLE_EXCEPTIONS.md"


def _contrast_ratio(foreground, background):
    def parse(value):
        value = value.lstrip("#")
        return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))

    def luminance(color):
        channels = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in color
        ]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    first = luminance(parse(foreground))
    second = luminance(parse(background))
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _source_lines_without_comments(path):
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield line_no, line


class DesignTokenTests(unittest.TestCase):
    def test_color_tokens_exist_in_both_themes(self):
        self.assertEqual(set(tokens.THEME_DARK), set(tokens.THEME_LIGHT))

    def test_theme_switch_updates_semantic_tokens(self):
        tokens.set_active_theme("light")
        self.assertEqual(tokens.COLOR_TEXT_LINK, tokens.THEME_LIGHT["COLOR_TEXT_LINK"])
        tokens.set_active_theme("dark")
        self.assertEqual(tokens.COLOR_TEXT_LINK, tokens.THEME_DARK["COLOR_TEXT_LINK"])

    def test_shared_stylesheet_uses_active_tokens(self):
        tokens.set_active_theme("light")
        light_qss = build_settings_qss()
        self.assertIn(tokens.COLOR_PRIMARY, light_qss)
        tokens.set_active_theme("dark")
        dark_qss = build_settings_qss()
        self.assertIn(tokens.COLOR_PRIMARY, dark_qss)

    def test_complex_widget_styles_are_centralized(self):
        from src.ui.stylesheet import (
            qss_document_page_editor,
            qss_slash_command_label,
            qss_slash_popup,
            qss_tool_call_step,
        )

        self.assertIn("QFrame#ToolCallStepRow:hover", qss_tool_call_step())
        self.assertIn(tokens.COLOR_OVERLAY_SELECTED, qss_slash_popup())
        self.assertIn(tokens.COLOR_TEXT_PRIMARY, qss_slash_command_label())
        self.assertIn(tokens.COLOR_INLINE_EDIT_FOCUS, qss_document_page_editor())

    def test_markdown_uses_theme_aware_link_and_code_colors(self):
        tokens.set_active_theme("dark")
        dark_html = markdown_to_html("[source](file:///tmp/source.pdf)\n\n`code`")
        self.assertIn(tokens.COLOR_TEXT_LINK, dark_html)
        self.assertIn(tokens.COLOR_CODE_BACKGROUND, dark_html)

        tokens.set_active_theme("light")
        light_html = markdown_to_html("[source](file:///tmp/source.pdf)\n\n`code`")
        self.assertIn(tokens.COLOR_TEXT_LINK, light_html)
        self.assertIn(tokens.COLOR_CODE_BACKGROUND, light_html)
        tokens.set_active_theme("dark")

    def test_menu_and_tooltip_qss_use_tokens(self):
        tokens.set_active_theme("dark")
        menu = qss_menu("AssistantMenu", selected_as_primary=True)
        self.assertIn(tokens.COLOR_PRIMARY, menu)
        self.assertIn(tokens.COLOR_TEXT_INVERSE, menu)
        self.assertIn(tokens.COLOR_BG_SURFACE, qss_tooltip())

    def test_no_hex_literals_outside_design_tokens(self):
        offenders = []
        for path in UI_ROOT.rglob("*.py"):
            if path.resolve() == TOKEN_FILE.resolve():
                continue
            for line_no, line in _source_lines_without_comments(path):
                if HEX_RE.search(line):
                    offenders.append(f"{path.relative_to(UI_ROOT.parent.parent)}:{line_no}:{line.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_rgba_literals_are_centralized_in_design_tokens(self):
        offenders = []
        for path in UI_ROOT.rglob("*.py"):
            if path.resolve() == TOKEN_FILE.resolve():
                continue
            for line_no, line in _source_lines_without_comments(path):
                if "rgba(" in line:
                    offenders.append(f"{path.relative_to(UI_ROOT.parent.parent)}:{line_no}:{line.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_local_style_exceptions_are_documented(self):
        self.assertTrue(STYLE_EXCEPTIONS.exists())
        exceptions = STYLE_EXCEPTIONS.read_text(encoding="utf-8")
        for path in (
            "document_dialog.py",
            "tool_call_widget.py",
            "slash_command_popup.py",
        ):
            self.assertIn(path, exceptions)

    def test_shared_widgets_do_not_use_literal_fixed_dimensions(self):
        offenders = []
        for name in (
            "audio_bars.py",
            "chat_bubble.py",
            "composer_bar.py",
            "hairline.py",
            "recording_indicator.py",
            "skill_tag.py",
            "status_label.py",
            "tool_call_widget.py",
            "window_chrome.py",
        ):
            path = UI_ROOT / "widgets" / name
            for line_no, line in _source_lines_without_comments(path):
                if FIXED_DIMENSION_LITERAL_RE.search(line):
                    offenders.append(f"{path.relative_to(UI_ROOT.parent.parent)}:{line_no}:{line.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_gray_scale_tokens_were_removed(self):
        self.assertFalse(any(key.startswith("COLOR_GRAY_") for key in tokens.THEME_DARK))

    def test_primary_button_text_meets_aa_contrast_in_both_themes(self):
        for theme_name, theme in (
            ("dark", tokens.THEME_DARK),
            ("light", tokens.THEME_LIGHT),
        ):
            for state in ("COLOR_PRIMARY", "COLOR_PRIMARY_HOVER", "COLOR_PRIMARY_ACTIVE"):
                ratio = _contrast_ratio(theme["COLOR_PRIMARY_TEXT"], theme[state])
                self.assertGreaterEqual(
                    ratio,
                    4.5,
                    f"Contraste insuffisant ({ratio:.2f}:1) pour {state} en thème {theme_name}",
                )

    def test_semantic_text_and_focus_colors_meet_contrast_targets(self):
        for theme_name, theme in (
            ("dark", tokens.THEME_DARK),
            ("light", tokens.THEME_LIGHT),
        ):
            for text_key in ("COLOR_TEXT_PRIMARY", "COLOR_TEXT_SECONDARY", "COLOR_TEXT_LINK"):
                ratio = _contrast_ratio(theme[text_key], theme["COLOR_BG_PAGE"])
                self.assertGreaterEqual(
                    ratio,
                    4.5,
                    f"Contraste insuffisant ({ratio:.2f}:1) pour {text_key} en thème {theme_name}",
                )
            focus_ratio = _contrast_ratio(theme["COLOR_PRIMARY"], theme["COLOR_BG_SURFACE"])
            self.assertGreaterEqual(
                focus_ratio,
                3.0,
                f"Anneau/focus insuffisant ({focus_ratio:.2f}:1) en thème {theme_name}",
            )


class SharedWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_window_chrome_and_status_label(self):
        from src.ui.widgets.hairline import HairlineSeparator
        from src.ui.widgets.status_label import StatusLabel
        from src.ui.widgets.window_chrome import WindowChrome

        chrome = WindowChrome("Transcript")
        self.assertEqual(chrome.title_label.text(), "Transcript")
        self.assertEqual(chrome.height(), tokens.HEADER_HEIGHT)
        line = HairlineSeparator()
        self.assertIn(tokens.COLOR_SEPARATOR, line.line.styleSheet())
        label = StatusLabel("ok", tone="success")
        self.assertIn(tokens.COLOR_SUCCESS_STRONG, label.styleSheet())
        tokens.set_active_theme("light")
        label.refresh_theme()
        self.assertIn(tokens.THEME_LIGHT["COLOR_SUCCESS_STRONG"], label.styleSheet())
        tokens.set_active_theme("dark")

    def test_chat_bubble_and_composer(self):
        from src.ui.widgets.chat_bubble import ChatBubble
        from src.ui.widgets.composer_bar import ComposerBar

        bubble = ChatBubble("user")
        bubble.set_html("Bonjour")
        self.assertEqual(bubble.objectName(), "UserBubble")
        composer = ComposerBar()
        self.assertEqual(composer.objectName(), "Composer")
        self.assertTrue(composer.question.placeholderText())
        bubble.refresh_theme()
        self.assertIn(tokens.COLOR_BG_SUBTLE, bubble.styleSheet())


class InteractiveStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        from src.ui.icons import initialize_icons

        cls.app = QApplication.instance() or QApplication([])
        initialize_icons()

    def tearDown(self):
        tokens.set_active_theme("dark")

    def test_shared_qss_declares_interactive_states(self):
        from src.ui.stylesheet import (
            build_settings_qss,
            qss_buttons,
            qss_header_icon_button,
            qss_inputs,
            qss_list_widget,
            qss_tool_button,
        )

        for block in (
            build_settings_qss(),
            qss_buttons(),
            qss_header_icon_button(),
            qss_inputs(),
            qss_tool_button(),
            qss_list_widget(),
        ):
            self.assertIn(":hover", block)
            self.assertIn(":focus", block)
            self.assertIn(":disabled", block)
        self.assertIn(":pressed", qss_buttons())
        self.assertIn(tokens.COLOR_PRIMARY, qss_header_icon_button())

    def test_icon_buttons_have_size_tooltip_and_states(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QEnterEvent, QIcon
        from PySide6.QtWidgets import QWidget

        from src.ui.widgets.animated_buttons import (
            AnimatedComposerButton,
            AnimatedHeaderButton,
        )

        host = QWidget()
        host.resize(120, 80)
        add = AnimatedComposerButton("add", host)
        add.setToolTip("Ajouter un document ou lancer une skill")
        header = AnimatedHeaderButton(QIcon(), "Fermer", host)
        add.move(0, 0)
        header.move(40, 0)
        host.show()
        host.activateWindow()
        self.app.processEvents()
        self.assertEqual(add.size(), add.BUTTON_SIZE)
        self.assertEqual(add.width(), tokens.BUTTON_SIZE_HEADER)
        self.assertEqual(header.size(), header.BUTTON_SIZE)
        self.assertTrue(add.toolTip())
        self.assertEqual(header.toolTip(), "Fermer")
        self.assertEqual(add.focusPolicy(), Qt.StrongFocus)
        self.assertEqual(header.focusPolicy(), Qt.StrongFocus)

        add.setFocus(Qt.TabFocusReason)
        self.app.processEvents()
        self.assertTrue(add.hasFocus())
        self.assertFalse(add.grab().isNull())

        add.setDown(True)
        self.assertTrue(add.isDown())
        self.assertFalse(add.grab().isNull())
        add.setDown(False)

        enter = QEnterEvent(QPointF(8, 8), QPointF(8, 8), QPointF(8, 8))
        add.enterEvent(enter)
        header.enterEvent(QEnterEvent(QPointF(8, 8), QPointF(8, 8), QPointF(8, 8)))
        self.assertTrue(header._is_hovered)
        self.assertFalse(add.grab().isNull())
        self.assertFalse(header.grab().isNull())

        add.setEnabled(False)
        header.setEnabled(False)
        self.assertFalse(add.isEnabled())
        muted = add.icon_color.name().upper()
        self.assertEqual(muted, tokens.COLOR_TEXT_MUTED.upper())
        self.assertFalse(add.grab().isNull())
        self.assertFalse(header.grab().isNull())
        host.close()

    def test_composer_tooltips_dimensions_and_loading_control(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget

        from src.ui.widgets.composer_bar import ComposerBar

        host = QWidget()
        host.resize(420, 80)
        bar = ComposerBar(host)
        host.show()
        host.activateWindow()
        self.app.processEvents()
        self.assertGreaterEqual(bar.minimumHeight(), 38)
        self.assertEqual(bar.add_button.toolTip(), "Ajouter un document ou lancer une skill")
        self.assertEqual(bar.mic.toolTip(), "Dicter")
        self.assertEqual(bar.send.toolTip(), "Envoyer")
        self.assertEqual(bar.stop_generation_button.toolTip(), "Arrêter la génération")
        self.assertEqual(bar.question.focusPolicy(), Qt.StrongFocus)
        bar.stop_generation_button.show()
        self.assertTrue(bar.stop_generation_button.isVisible())
        bar.send.show()
        bar.stop_generation_button.show()
        self.app.processEvents()
        chain = []
        current = bar.add_button
        for _ in range(12):
            current = current.nextInFocusChain()
            if current is bar.add_button:
                break
            if (
                current.isVisible()
                and current.isEnabled()
                and int(current.focusPolicy()) & int(Qt.TabFocus)
            ):
                chain.append(current)
        self.assertGreaterEqual(len(chain), 4)
        self.assertIs(chain[0], bar.question)
        self.assertIs(chain[1], bar.mic)
        self.assertIs(chain[2], bar.send)
        self.assertIs(chain[3], bar.stop_generation_button)
        bar.add_button.setFocus(Qt.TabFocusReason)
        self.app.processEvents()
        self.assertTrue(bar.add_button.hasFocus())
        host.close()

    def test_status_label_tones_and_long_text(self):
        from src.ui.widgets.status_label import StatusLabel
        from src.ui.widgets.window_chrome import WindowChrome

        for tone, token_name in (
            ("success", "COLOR_SUCCESS_STRONG"),
            ("danger", "COLOR_DANGER"),
            ("warning", "COLOR_WARNING"),
            ("loading", "COLOR_PRIMARY"),
            ("muted", "COLOR_TEXT_SECONDARY"),
        ):
            label = StatusLabel("état", tone=tone)
            self.assertIn(getattr(tokens, token_name), label.styleSheet())
        long_title = "Titre " + ("très long " * 24)
        chrome = WindowChrome(long_title)
        chrome.setFixedWidth(280)
        self.assertEqual(chrome.title_label.text(), long_title)
        self.assertEqual(chrome.height(), tokens.HEADER_HEIGHT)
        long_label = StatusLabel("Statut " + ("erreur " * 30), tone="danger")
        long_label.setWordWrap(True)
        long_label.setFixedWidth(200)
        self.assertGreater(long_label.sizeHint().height(), 16)

    def test_skill_tag_and_loading_widgets(self):
        from PySide6.QtCore import QSize

        from src.ui.widgets.skill_tag import SkillTag
        from src.ui.widgets.thinking_dots import GenerationSpinner, ThinkingDots

        tag = SkillTag(framed=True)
        tag.set_tag({"title": "Skill " + ("très longue " * 12)})
        self.assertTrue(tag.isVisible())
        self.assertEqual(tag.icon_label.width(), tokens.ICON_SIZE_SKILL)
        self.assertGreater(len(tag.title_label.text()), 40)
        self.assertFalse(tag.grab().isNull())

        dots = ThinkingDots()
        spinner = GenerationSpinner()
        self.assertEqual(dots.size(), QSize(44, 22))
        self.assertEqual(spinner.size(), QSize(22, 22))
        self.assertFalse(dots.grab().isNull())
        self.assertFalse(spinner.grab().isNull())
        dots.timer.stop()
        spinner._timer.stop()

    def test_chat_bubble_grows_with_long_text(self):
        from src.ui.widgets.chat_bubble import ChatBubble

        short = ChatBubble("assistant")
        short.set_html("<p>Court</p>")
        long = ChatBubble("assistant")
        long.setFixedWidth(320)
        long.set_html("<p>" + ("Paragraphe long. " * 40) + "</p>")
        self.assertGreater(long.height(), short.height())


class MarkdownBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_qtextbrowser_renders_lists_code_and_links(self):
        from src.ui.widgets.chat_bubble import ChatBubble

        source = "## Titre\n\nUn paragraphe assez long pour vérifier le retour à la ligne Qt.\n\n- puce une\n- puce deux\n\n1. premier\n2. deuxième\n\n`inline`\n\n[source](file:///tmp/source.pdf)\n\n```\nprint('ok')\n```"
        html = markdown_to_html(source)
        self.assertIn("<ul", html)
        self.assertIn("<ol", html)
        self.assertIn("<pre", html)
        self.assertIn("file:///tmp/source.pdf", html)
        self.assertIn(tokens.COLOR_TEXT_LINK, html)

        bubble = ChatBubble("assistant")
        bubble.setFixedWidth(360)
        bubble.set_html(html)
        self.app.processEvents()
        browser = bubble.browser
        plain = browser.toPlainText()
        self.assertIn("Titre", plain)
        self.assertIn("puce une", plain)
        self.assertIn("premier", plain)
        self.assertIn("inline", plain)
        self.assertIn("print('ok')", plain)
        self.assertIn("source", plain)
        found_link = False
        block = browser.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid() and fragment.charFormat().isAnchor():
                    found_link = True
                    break
                it += 1
            if found_link:
                break
            block = block.next()
        self.assertTrue(found_link)


class PersistentWindowThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        from src.ui.icons import initialize_icons

        cls.app = QApplication.instance() or QApplication([])
        initialize_icons()

    def tearDown(self):
        tokens.set_active_theme("dark")

    def test_runtime_info_dialog_refresh_theme(self):
        from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog

        dialog = RuntimeInfoDialog()
        tokens.set_active_theme("light")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_LIGHT["COLOR_BG_PAGE"], dialog.styleSheet())
        tokens.set_active_theme("dark")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_DARK["COLOR_BG_PAGE"], dialog.styleSheet())
        dialog.close()
        dialog.deleteLater()

    def test_settings_dialog_refresh_theme(self):
        from copy import deepcopy

        from src.config.schema import DEFAULT_CONFIG
        from src.ui.windows.settings_dialog import SettingsDialog

        dialog = SettingsDialog(deepcopy(DEFAULT_CONFIG))
        tokens.set_active_theme("light")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_LIGHT["COLOR_BG_PAGE"], dialog.styleSheet())
        tokens.set_active_theme("dark")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_DARK["COLOR_BG_PAGE"], dialog.styleSheet())
        dialog.close()
        dialog.deleteLater()

    def test_document_dialog_refresh_theme(self):
        from src.ui.windows.document_dialog import DocumentDialog

        dialog = DocumentDialog()
        tokens.set_active_theme("light")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_LIGHT["COLOR_BG_ACRYLIC"], dialog.styleSheet())
        tokens.set_active_theme("dark")
        dialog.refresh_theme()
        self.assertIn(tokens.THEME_DARK["COLOR_BG_ACRYLIC"], dialog.styleSheet())
        dialog.close()
        dialog.deleteLater()

    def test_apply_app_theme_refreshes_open_runtime_dialog(self):
        from src.ui.theme import apply_app_theme
        from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog

        dialog = RuntimeInfoDialog()
        apply_app_theme(self.app, "light")
        self.assertEqual(tokens.CURRENT_THEME, "light")
        self.assertIn(tokens.THEME_LIGHT["COLOR_BG_PAGE"], dialog.styleSheet())
        apply_app_theme(self.app, "dark")
        self.assertIn(tokens.THEME_DARK["COLOR_BG_PAGE"], dialog.styleSheet())
        dialog.close()
        dialog.deleteLater()

    def test_skill_icons_are_declared(self):
        skills_root = Path(__file__).resolve().parents[1] / "skills"
        missing = []
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            if not (skill_dir / "skill.py").exists():
                continue
            if not (skill_dir / "icon.svg").exists() and not (skill_dir / "icon.png").exists():
                missing.append(skill_dir.name)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
