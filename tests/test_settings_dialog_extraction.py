"""Tests de structure et de non-regression independants de Qt."""
import ast
import unittest
from pathlib import Path

WINDOWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "windows"
GROUPS = {
    "settings_runtime_controller": (
        "shutdown_background_threads", "refresh_runtime_status", "check_nvidia_status",
        "on_nvidia_thread_finished", "update_nvidia_status", "schedule_server_status_check",
        "check_server_status", "on_status_thread_finished", "update_server_status",
    ),
    "settings_actions_controller": (
        "populate_list", "on_action_selected", "update_action_field", "add_action", "del_action", "move_action",
    ),
    "settings_server_controller": (
        "browse_server_executable", "browse_server_model", "collect_server_config",
        "start_local_server", "stop_local_server",
    ),
    "settings_audio_controller": ("refresh_audio_devices", "toggle_microphone_test"),
    "settings_appearance_controller": (
        "_on_theme_preview_changed", "refresh_theme", "_refresh_ctrl9_preview",
    ),
    "settings_config_controller": ("save",),
    "settings_window_behavior": ("apply_effects",),
}
VIEW_SECTIONS = (
    "build_shell", "build_llm_section", "build_voice_section",
    "build_shortcuts_section", "build_footer",
)

class RefactoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((WINDOWS / "settings_dialog.py").read_text(encoding="utf-8"))
        dialog = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SettingsDialog")
        cls.methods = {n.name: n for n in dialog.body if isinstance(n, ast.FunctionDef)}

    def test_modules_compile(self):
        for path in WINDOWS.glob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_compatibility_facades(self):
        for module, names in GROUPS.items():
            tree = ast.parse((WINDOWS / (module + ".py")).read_text(encoding="utf-8"))
            functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
            for name in names:
                with self.subTest(name=name):
                    method, function = self.methods[name], functions[name]
                    self.assertEqual(ast.dump(method.args), ast.dump(function.args))
                    self.assertEqual(len(method.body), 1)
                    statement = method.body[0]
                    self.assertIsInstance(statement, ast.Return)
                    call = statement.value
                    self.assertIsInstance(call, ast.Call)
                    self.assertEqual(call.func.value.id, "_" + module)
                    self.assertEqual(call.func.attr, name)
                    self.assertEqual([a.id for a in call.args], [a.arg for a in method.args.args])

    def test_view_orchestration_order(self):
        view = ast.parse((WINDOWS / "settings_dialog_view.py").read_text(encoding="utf-8"))
        names = [n.name for n in view.body if isinstance(n, ast.FunctionDef)]
        self.assertEqual(names, list(VIEW_SECTIONS))
        calls = [n for n in ast.walk(self.methods["initUI"]) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == "_settings_dialog_view"]
        self.assertEqual([c.func.attr for c in calls], list(VIEW_SECTIONS))

    def test_qt_lifecycle_overrides_remain_on_dialog(self):
        for name in ("eventFilter", "moveEvent", "showEvent", "done", "closeEvent"):
            self.assertIn(name, self.methods)

    def test_nvidia_status_display(self):
        tree = ast.parse((WINDOWS / "settings_runtime_controller.py").read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "update_nvidia_status")
        namespace = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gpu>", "exec"), namespace)  # noqa: S102
        class Label:
            def __init__(self): self.text = self.tooltip = self.tone = None
            def setText(self, value): self.text = value
            def setToolTip(self, value): self.tooltip = value
            def set_tone(self, value, **kwargs): self.tone = value
        class Dialog: pass
        dialog = Dialog()
        dialog.gpu_pstate_label = Label()
        dialog.gpu_detail_label = Label()
        namespace["update_nvidia_status"](dialog, True, "P0/P8", "GPU")
        self.assertEqual(dialog.gpu_pstate_label.tone, "success")
        self.assertEqual(dialog.gpu_detail_label.text, "GPU")
        namespace["update_nvidia_status"](dialog, False, "", "")
        self.assertEqual(dialog.gpu_pstate_label.tone, "muted")
        self.assertEqual(dialog.gpu_detail_label.text, "")

if __name__ == "__main__":
    unittest.main()
