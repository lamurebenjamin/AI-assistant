import importlib
import tempfile
import unittest
from pathlib import Path

from core.skill_manager import SkillError, SkillManager


class SkillManagerTests(unittest.TestCase):
    def make_skill(self, root, name="demo"):
        root = Path(root) / "skills"
        root.mkdir(exist_ok=True)
        package = root / name
        package.mkdir()
        (root / "__init__.py").write_text("", encoding="utf-8")
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "icon.svg").write_text("<svg/>", encoding="utf-8")
        class_name = name.title() + "Skill"
        tool_name = "add" if name == "demo" else f"{name}_add"
        echo_name = "echo" if name == "demo" else f"{name}_echo"
        (package / "skill.py").write_text(
            f"class {class_name}:\n"
            f"    name = '{name}'\n"
            "    icon = 'icon.svg'\n"
            "    def get_tools(self):\n"
            f"        def {tool_name}(value):\n"
            "            return value + 1\n"
            f"        return [{{'name': '{echo_name}', 'description': 'Echo', 'parameters': {{'type': 'object'}}}}, {tool_name}]\n"
            "    def execute(self, tool, arguments):\n"
            "        return tool + ':' + arguments['value']\n",
            encoding="utf-8",
        )

    def test_discovery_tools_execution_and_description(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_skill(directory)
            manager = SkillManager(Path(directory) / "skills")
            self.assertEqual(manager.discover(), ["demo"])
            self.assertEqual(manager.list_skills(), ["demo"])
            self.assertEqual(manager.execute_tool("add", {"value": 2}), 3)
            self.assertEqual(manager.execute("demo", "echo", {"value": "ok"}), "echo:ok")
            self.assertEqual(manager.get_skill_icon("DEMO"), str(Path(directory, "skills", "demo", "icon.svg").resolve()))
            self.assertEqual(manager.describe_for_llm()[0]["function"]["name"], "add")

    def test_reload_discovers_new_skill_and_errors_are_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_skill(directory)
            manager = SkillManager(Path(directory) / "skills")
            manager.discover()
            self.make_skill(directory, "other")
            importlib.invalidate_caches()
            self.assertEqual(manager.reload(), ["demo", "other"])
            with self.assertRaises(SkillError):
                manager.get_tool("missing")
            with self.assertRaises(SkillError):
                manager.execute("other", "add", {"value": 1})

    def test_invalid_skill_directory_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory) / "skills"
            skills.mkdir()
            (skills / "broken").mkdir()
            (skills / "broken" / "skill.py").write_text("x = 1", encoding="utf-8")
            self.assertEqual(SkillManager(Path(directory) / "skills").discover(), [])

    def test_fastmcp_skill_and_unified_server(self):
        from core.mcp_compat import MCP_AVAILABLE
        if not MCP_AVAILABLE:
            self.skipTest("mcp library not available")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            root.mkdir()
            (root / "__init__.py").write_text("", encoding="utf-8")
            pkg = root / "mcpdemo"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "skill.py").write_text(
                "from core.mcp_compat import FastMCP\n"
                "mcp = FastMCP('mcpdemo')\n"
                "@mcp.tool(name='mcp_multiply', description='Multiplie deux entiers.')\n"
                "def mcp_multiply(a: int, b: int) -> int:\n"
                "    return a * b\n"
                "class McpdemoSkill:\n"
                "    name = 'mcpdemo'\n"
                "    mcp = mcp\n",
                encoding="utf-8",
            )
            import sys
            for m in list(sys.modules):
                if m == "skills" or m.startswith("skills."):
                    del sys.modules[m]
            importlib.invalidate_caches()
            manager = SkillManager(root)
            discovered = manager.discover()
            self.assertIn("mcpdemo", discovered)
            self.assertIn("mcp_multiply", manager.tools)
            res = manager.execute_tool("mcp_multiply", {"a": 6, "b": 7})
            self.assertEqual(res, 42)
            unified = manager.get_unified_mcp_server("Test-Server")
            self.assertIsNotNone(unified)


if __name__ == "__main__":
    unittest.main()
