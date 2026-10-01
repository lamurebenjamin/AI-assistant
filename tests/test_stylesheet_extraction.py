"""Tests de non-regression du decoupage QSS, sans dependance Qt ni projet complet."""
import ast
import builtins
import hashlib
import importlib
import inspect
import json
import symtable
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui"
HERE = Path(__file__).resolve().parent
# Explicit extraction scope: stylesheet_document.py belongs to the existing project
# and must not be included in AST, global-reference, or dependency checks.
EXTRACTED_MODULES = (
    "stylesheet.py",
    "stylesheet_base.py",
    "stylesheet_settings.py",
    "stylesheet_conversation.py",
    "stylesheet_assistant.py",
    "stylesheet_tools.py",
    "stylesheet_builders.py",
)


def extracted_paths():
    """Validate that every module in this patch exists, then yield it."""
    for name in EXTRACTED_MODULES:
        path = UI / name
        if not path.is_file():
            raise AssertionError(f"Missing extracted stylesheet module: {path}")
        yield path


DOCUMENT_NAMES = (
    "qss_ctrl9_preview", "qss_document_dialog", "qss_document_page_dash",
    "qss_document_page_editor", "qss_document_page_name",
    "qss_document_preview_dialog", "qss_tool_call_step", "qss_tool_code_browser",
)
VARIANTS = {
    "qss_title_label": [(2,), (-1,)],
    "qss_header_icon_button": [("CloseButton",)],
    "qss_menu": [("ContextMenu",), ({"object_name": "Popup", "font_size": "19px", "selected_as_primary": True, "padding": 8},)],
    "qss_settings_emphasis": [(16, True), (None, False)],
    "qss_tool_group_header": [("#f00",)],
    "qss_thinking_details": [(18,)],
    "qss_skill_tag_title": [("#fff", 14, 700)],
    "qss_timeline_header_title": [("#f00",)],
    "qss_status_label": [("#f00", "14px", 700, True)],
    "qss_shimmer_status_label": [(2,)],
    "build_acrylic_window_qss": [(2,)],
}


def cases(name, function):
    signature = inspect.signature(function)
    required = {
        n: "14px" if n == "size" else "#f00"
        for n, parameter in signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    yield "required", (), required
    for i, value in enumerate(VARIANTS.get(name, [])):
        if len(value) == 1 and isinstance(value[0], dict):
            yield "variant_" + str(i), (), value[0]
        else:
            yield "variant_" + str(i), value, {}


class StylesheetExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = {key: value for key, value in sys.modules.items() if key == "src" or key.startswith("src.")}
        for key in cls.saved:
            del sys.modules[key]
        src = types.ModuleType("src")
        src.__path__ = [str(ROOT / "src")]
        ui = types.ModuleType("src.ui")
        ui.__path__ = [str(UI)]
        tokens = types.ModuleType("src.ui.design_tokens")
        tokens.dark = False
        def get_token(name):
            if name == "is_dark_theme":
                return lambda: tokens.dark
            if name.startswith(("SIZE_", "RADIUS_")):
                return "15px" if tokens.dark else "14px"
            if name.startswith("FONT_"):
                return "Consolas" if tokens.dark else "Arial"
            if name.startswith("COLOR_"):
                return "#abcdef" if tokens.dark else "#123456"
            if name in {"SCROLLBAR_WIDTH", "SCROLLBAR_THUMB_MIN", "SPINBOX_BUTTON_WIDTH", "HAIRLINE_HEIGHT"}:
                return 6 if tokens.dark else 5
            raise AttributeError(name)
        tokens.__getattr__ = get_token
        document = types.ModuleType("src.ui.stylesheet_document")
        for name in DOCUMENT_NAMES:
            setattr(document, name, lambda name=name: "document " + name)
        sys.modules.update({src.__name__: src, ui.__name__: ui, tokens.__name__: tokens, document.__name__: document})
        cls.tokens = tokens
        cls.document = document
        cls.stylesheet = importlib.import_module("src.ui.stylesheet")

    @classmethod
    def tearDownClass(cls):
        for key in list(sys.modules):
            if key == "src" or key.startswith("src."):
                del sys.modules[key]
        sys.modules.update(cls.saved)

    def test_extraction_scope_excludes_existing_document_styles(self):
        names = {path.name for path in extracted_paths()}
        self.assertEqual(names, set(EXTRACTED_MODULES))
        self.assertNotIn("stylesheet_document.py", names)
        self.assertEqual(len(names), len(EXTRACTED_MODULES))

    def test_all_modules_compile_and_original_function_bodies_unchanged(self):
        reference = json.loads((HERE / "stylesheet_ast_reference.json").read_text(encoding="utf-8"))
        found = {}
        for path in extracted_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            compile(tree, str(path), "exec")
            if path.name == "stylesheet.py":
                self.assertFalse(any(isinstance(n, ast.FunctionDef) for n in tree.body))
                continue
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    self.assertNotIn(node.name, found)
                    found[node.name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        self.assertEqual(found, reference)

    def test_facade_exports_every_function_and_keeps_original_all(self):
        reference = json.loads((HERE / "stylesheet_ast_reference.json").read_text(encoding="utf-8"))
        for name in reference:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(self.stylesheet, name)))
        self.assertEqual(self.stylesheet.__all__, list(DOCUMENT_NAMES))
        for name in DOCUMENT_NAMES:
            self.assertIs(getattr(self.stylesheet, name), getattr(self.document, name))

    def test_qss_outputs_match_original_snapshots_in_both_themes(self):
        reference = json.loads((HERE / "stylesheet_qss_reference.json").read_text(encoding="utf-8"))
        actual = {}
        for dark in (False, True):
            self.tokens.dark = dark
            for name in json.loads((HERE / "stylesheet_ast_reference.json").read_text(encoding="utf-8")):
                fn = getattr(self.stylesheet, name)
                for label, args, kwargs in cases(name, fn):
                    with self.subTest(dark=dark, function=name, case=label):
                        value = fn(*args, **kwargs)
                        self.assertIsInstance(value, str)
                        actual[f"{int(dark)}:{name}:{label}"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
        self.assertEqual(actual, reference)

    def test_no_unresolved_global_references(self):
        for path in extracted_paths():
            table = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
            bound = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
            used = set()
            def walk(scope, _used: set = used):
                for symbol in scope.get_symbols():
                    if symbol.is_referenced() and symbol.is_global():
                        _used.add(symbol.get_name())
                for child in scope.get_children():
                    walk(child)
            walk(table)
            self.assertEqual(used - bound - set(dir(builtins)), set(), path.name)

    def test_dependency_graph_has_no_cycles(self):
        dependencies = {}
        for path in extracted_paths():
            if path.stem == "stylesheet":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            dependencies[path.stem] = {n.module.removeprefix("src.ui.") for n in tree.body if isinstance(n, ast.ImportFrom) and n.module.startswith("src.ui.stylesheet_")}
        def visit(name, stack):
            self.assertNotIn(name, stack)
            for dependency in dependencies.get(name, ()):
                visit(dependency, stack | {name})
        for name in dependencies:
            visit(name, set())

if __name__ == "__main__":
    unittest.main()
