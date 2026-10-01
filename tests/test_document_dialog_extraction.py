"""Tests statiques et de comportement pur pour le refactoring du dialogue."""
import ast
import re
import unittest
from pathlib import Path

WINDOWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "windows"
GROUPS = {
    "document_dialog_view": ("_build_ui",),
    "document_skill_controller": (
        "_create_add_menu", "_show_add_menu", "_on_skill_tool_selected",
        "_skill_tool_details", "_set_skill_tag", "_clear_skill_tag_when_erased",
        "_clear_skill_tag", "_select_skill_tool", "_build_slash_actions",
        "_position_slash_popup", "_on_slash_triggered", "_on_slash_dismissed",
        "_on_slash_action_selected",
    ),
    "document_attachment_renderer": (
        "_answer_without_sources", "_attachment_preview_html",
        "_create_pdf_fallback_pixmap",
    ),
    "document_source_preview": ("_show_source_image_large",),
    "document_window_behavior": (
        "_header_press", "_header_move", "_header_release", "toggle_collapse",
        "_update_rounded_masks", "_apply_effects",
    ),
}

class DocumentDialogExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dialog = ast.parse((WINDOWS / "document_dialog.py").read_text(encoding="utf-8"))
        cls.dialog_class = next(n for n in cls.dialog.body if isinstance(n, ast.ClassDef) and n.name == "DocumentDialog")
        cls.methods = {n.name: n for n in cls.dialog_class.body if isinstance(n, ast.FunctionDef)}

    def test_all_python_modules_compile(self):
        for path in WINDOWS.glob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_facades_preserve_names_signatures_and_delegation(self):
        for module, names in GROUPS.items():
            moved = ast.parse((WINDOWS / (module + ".py")).read_text(encoding="utf-8"))
            functions = {n.name: n for n in moved.body if isinstance(n, ast.FunctionDef)}
            for name in names:
                with self.subTest(module=module, method=name):
                    facade = self.methods[name]
                    implementation = functions[name]
                    self.assertEqual(ast.dump(facade.args), ast.dump(implementation.args))
                    self.assertEqual(len(facade.body), 1)
                    self.assertIsInstance(facade.body[0], ast.Return)
                    call = facade.body[0].value
                    self.assertIsInstance(call, ast.Call)
                    self.assertEqual(call.func.value.id, "_" + module)
                    self.assertEqual(call.func.attr, name)
                    expected = [a.arg for a in facade.args.args]
                    self.assertEqual([a.id for a in call.args], expected)

    def test_fallback_pixmap_keeps_staticmethod_contract(self):
        facade = self.methods["_create_pdf_fallback_pixmap"]
        self.assertEqual([d.id for d in facade.decorator_list], ["staticmethod"])

    def test_sources_cleanup(self):
        module = ast.parse((WINDOWS / "document_attachment_renderer.py").read_text(encoding="utf-8"))
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "_answer_without_sources")
        namespace = {"re": re}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<pure method>", "exec"), namespace)  # noqa: S102
        clean = namespace["_answer_without_sources"]
        self.assertEqual(clean(None, "  Reponse\n\n## Sources\n[1]  "), "Reponse")
        self.assertEqual(clean(None, "Texte\nSources:\n[1]"), "Texte")
        self.assertEqual(clean(None, ""), "")

if __name__ == "__main__":
    unittest.main()
