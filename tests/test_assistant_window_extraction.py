"""Tests statiques autonomes du patch AssistantWindow (sans dependances Qt)."""
import ast
import builtins
import symtable
import unittest
from pathlib import Path

WINDOWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "windows"
GROUPS = {
    "assistant_window_view": ("initUI", "refresh_theme", "update_window_title", "animate_copy_button", "apply_native_window_effects"),
    "assistant_window_runtime": ("show_runtime_information", "_display_runtime_information", "_on_runtime_info_finished"),
    "assistant_window_clipboard": ("get_selected_text", "copy_response", "open_response_link"),
    "assistant_window_document_session": ("start_document_analysis", "update_document_tool_event", "update_document_text", "update_document_thinking", "open_document_source", "_open_first_cited_pdf", "handle_document_error", "on_document_finished"),
    "assistant_window_request_controller": ("trigger_action", "execute_action", "update_thinking", "handle_voice_request_error", "update_tool_event", "on_finished", "stop_generation"),
    "assistant_window_lifecycle": ("quit_application", "shutdown_background_threads", "open_settings"),
}
MANAGER_METHODS = {"show_runtime_information", "start_document_analysis", "execute_action", "quit_application"}

class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((WINDOWS / "assistant_window.py").read_text(encoding="utf-8"))
        dialog = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AssistantWindow")
        cls.methods = {n.name: n for n in dialog.body if isinstance(n, ast.FunctionDef)}

    def test_modules_compile(self):
        for path in WINDOWS.glob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_facades_delegate_without_changing_signatures(self):
        for module, names in GROUPS.items():
            tree = ast.parse((WINDOWS / (module + ".py")).read_text(encoding="utf-8"))
            moved = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
            for name in names:
                with self.subTest(module=module, method=name):
                    facade = self.methods[name]
                    impl = moved[name]
                    expected = [a.arg for a in facade.args.args]
                    self.assertEqual([a.arg for a in impl.args.args], expected)
                    self.assertEqual(ast.get_docstring(facade), ast.get_docstring(impl))
                    self.assertIsInstance(facade.body[-1], ast.Return)
                    call = facade.body[-1].value
                    self.assertIsInstance(call, ast.Call)
                    self.assertEqual(call.func.value.id, "_" + module)
                    self.assertEqual(call.func.attr, name)
                    self.assertEqual([arg.id for arg in call.args], expected)
                    if name in MANAGER_METHODS:
                        self.assertEqual([kw.arg for kw in call.keywords], ["server_manager"])
                        self.assertEqual(call.keywords[0].value.id, "LLAMA_SERVER_MANAGER")
                        self.assertEqual([a.arg for a in impl.args.kwonlyargs], ["server_manager"])
                    else:
                        self.assertEqual(call.keywords, [])

    def test_no_missing_global_names(self):
        for path in WINDOWS.glob("*.py"):
            with self.subTest(path=path.name):
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
                self.assertEqual(used - bound - set(dir(builtins)), set())

    def test_document_response_accumulation(self):
        tree = ast.parse((WINDOWS / "assistant_window_document_session.py").read_text(encoding="utf-8"))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "update_document_text")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "<extracted>", "exec"), namespace)  # noqa: S102
        class Dialog:
            def __init__(self): self.chunks = []
            def append_response(self, text): self.chunks.append(text)
        class Window: pass
        window = Window(); window.response_text = ""; window.document_dialog = Dialog()
        namespace["update_document_text"](window, "bonjour ")
        namespace["update_document_text"](window, "monde")
        self.assertEqual(window.response_text, "bonjour monde")
        self.assertEqual(window.document_dialog.chunks, ["bonjour ", "monde"])

if __name__ == "__main__": unittest.main()
