"""Gestionnaire modulaire des skills de l'assistant IA."""
from __future__ import annotations

import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, TypedDict

LOGGER = logging.getLogger(__name__)


class SkillError(Exception):
    """Erreur liée au chargement ou à l'exécution d'un skill."""


class ToolDefinition(TypedDict, total=False):
    """Contrat d'un outil exposé au modèle ou exécuté par un skill."""

    name: str
    skill: str
    description: str
    function: Any
    parameters: dict[str, Any]


class SkillManager:
    """Découvre, enregistre et exécute les skills présents dans /skills."""

    def __init__(self, skills_directory: str | Path | None = None):
        self.skills_directory = (
            Path(skills_directory).resolve()
            if skills_directory
            else Path(__file__).resolve().parent.parent / "skills"
        )
        self.skills: dict[str, Any] = {}
        self.tools: dict[str, dict[str, Any]] = {}

    def discover(self) -> list[str]:
        """Charge tous les dossiers de skills contenant un skill.py."""
        self.skills.clear()
        self.tools.clear()
        if not self.skills_directory.is_dir():
            LOGGER.warning("Dossier skills introuvable : %s", self.skills_directory)
            return []

        # Le dossier racine du projet doit être importable pour
        # 'skills.mon_skill.skill'.
        project_root = str(self.skills_directory.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        loaded = []
        for directory in sorted(self.skills_directory.iterdir()):
            if not directory.is_dir() or directory.name.startswith("_"):
                continue
            if not (directory / "skill.py").is_file():
                continue
            try:
                skill = self._load_skill(directory.name)
                name = self._skill_name(skill)
                if name in self.skills:
                    raise SkillError(f"Skill déjà enregistré : {name}")
                self.skills[name] = skill
                self._register_tools(name, skill)
                loaded.append(name)
            except Exception:
                LOGGER.exception("Impossible de charger le skill '%s'", directory.name)
        return loaded

    def _load_skill(self, package_name: str) -> Any:
        if "skills" in sys.modules and hasattr(sys.modules["skills"], "__path__"):
            skills_dir_str = str(self.skills_directory)
            if skills_dir_str not in sys.modules["skills"].__path__:
                sys.modules["skills"].__path__.insert(0, skills_dir_str)
        module = importlib.import_module(f"skills.{package_name}.skill")
        candidates = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ and obj.__name__.endswith("Skill"):
                candidates.append(obj)
        if candidates:
            if len(candidates) > 1:
                LOGGER.warning("Plusieurs classes *Skill dans %s ; utilisation de %s", module.__name__, candidates[0].__name__)
            inst = candidates[0]()
            if not getattr(inst, "mcp", None) and hasattr(module, "mcp"):
                inst.mcp = module.mcp
            return inst

        # Si aucune classe *Skill, vérifier si le module définit un serveur MCP 'mcp'
        mcp_obj = getattr(module, "mcp", None) or getattr(module, "server", None)
        if mcp_obj is not None:
            class _ModuleSkillWrapper:
                name = package_name
                mcp = mcp_obj
                icon = getattr(module, "icon", None)
            return _ModuleSkillWrapper()

        raise SkillError(f"Aucune classe *Skill ni serveur MCP dans skills.{package_name}.skill")

    @staticmethod
    def _skill_name(skill: Any) -> str:
        name = getattr(skill, "name", None)
        if not name and hasattr(skill, "mcp") and getattr(skill.mcp, "name", None):
            name = skill.mcp.name
        if not name:
            name = skill.__class__.__name__.removesuffix("Skill")
        return str(name).strip().lower()

    def _register_tools(self, skill_name: str, skill: Any) -> None:
        # 1. Enregistrement natif depuis FastMCP / MCPServer
        mcp_server = getattr(skill, "mcp", None) or getattr(skill, "server", None)
        if mcp_server is not None and hasattr(mcp_server, "_tool_manager"):
            try:
                for tool in mcp_server._tool_manager.list_tools():
                    tool_name = tool.name
                    if tool_name in self.tools:
                        raise SkillError(f"Outil déjà enregistré : {tool_name}")
                    self.tools[tool_name] = {
                        "name": tool_name,
                        "skill": skill_name,
                        "description": tool.description or "",
                        "parameters": tool.parameters or {},
                        "function": tool.fn,
                        "is_async": getattr(tool, "is_async", False),
                        "mcp_server": mcp_server,
                        "return_direct": getattr(
                            tool.fn,
                            "return_direct",
                            getattr(tool, "return_direct", False),
                        ),
                    }
            except Exception:
                LOGGER.exception("Erreur lors de la lecture des outils MCP du skill '%s'", skill_name)

        # 2. Enregistrement classique via get_tools() pour rétrocompatibilité
        if hasattr(skill, "get_tools"):
            for tool in skill.get_tools() or []:
                if callable(tool):
                    name = tool.__name__
                    info = {"name": name, "skill": skill_name, "function": tool,
                            "description": inspect.getdoc(tool) or "",
                            "parameters": getattr(tool, "parameters", {})}
                elif isinstance(tool, dict):
                    name = str(tool.get("name", "")).strip()
                    if not name:
                        continue
                    info = dict(tool)
                    info["name"] = name
                    info["skill"] = skill_name
                    info.setdefault("description", "")
                else:
                    continue
                if name in self.tools:
                    # Ne pas dupliquer si déjà enregistré via FastMCP
                    if self.tools[name].get("function") is info.get("function"):
                        continue
                    raise SkillError(f"Outil déjà enregistré : {name}")
                self.tools[name] = info

    def list_skills(self) -> list[str]:
        return sorted(self.skills)

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": name, "skill": info["skill"], "description": info.get("description", "")}
            for name, info in sorted(self.tools.items())
        ]

    def get_skill(self, skill_name: str) -> Any:
        try:
            return self.skills[skill_name.strip().lower()]
        except KeyError as exc:
            raise SkillError(f"Skill inconnu : {skill_name}") from exc

    def get_skill_icon(self, skill_name: str) -> str | None:
        """Retourne le chemin d'une icône SVG ou PNG déclarée par un skill."""
        skill = self.get_skill(skill_name)
        icon = getattr(skill, "icon", None)
        if not icon:
            return None

        icon_path = Path(str(icon)).expanduser()
        if not icon_path.is_absolute():
            icon_path = self.skills_directory / skill_name.strip().lower() / icon_path
        return str(icon_path.resolve())

    def get_tool(self, tool_name: str) -> dict[str, Any]:
        key = tool_name.strip()
        if key in self.tools:
            return self.tools[key]
        if key == "Détails" and "Details" in self.tools:
            return self.tools["Details"]
        if key == "Details" and "Détails" in self.tools:
            return self.tools["Détails"]
        raise SkillError(f"Outil inconnu : {tool_name}")

    def execute(self, skill_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Exécute un outil en vérifiant qu'il appartient au skill demandé."""
        info = self.get_tool(tool_name)
        skill_name = skill_name.strip().lower()
        if info["skill"] != skill_name:
            raise SkillError(
                f"L'outil '{tool_name}' appartient à '{info['skill']}', pas à '{skill_name}'."
            )
        arguments = arguments or {}
        function = info.get("function")
        if callable(function):
            if info.get("is_async", False):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(asyncio.run, function(**arguments)).result()
                return asyncio.run(function(**arguments))
            return function(**arguments)
        skill = self.get_skill(skill_name)
        if hasattr(skill, "execute"):
            return skill.execute(tool_name, arguments)
        raise SkillError(f"Impossible d'exécuter '{tool_name}'.")

    def execute_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Exécute directement un outil sans connaître son skill."""
        info = self.get_tool(tool_name)
        return self.execute(info["skill"], tool_name, arguments)

    def describe_for_llm(self) -> list[dict[str, Any]]:
        """Retourne les définitions de tools au format OpenAI/llama.cpp."""
        definitions = []
        for name, info in sorted(self.tools.items()):
            parameters = info.get("parameters") or {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(info.get("description") or ""),
                    "parameters": parameters,
                },
            })
        return definitions

    def get_unified_mcp_server(self, name: str = "Assistant-Skills") -> Any:
        """Crée et retourne un serveur FastMCP combinant tous les outils enregistrés."""
        from core.mcp_compat import FastMCP
        if FastMCP is None:
            raise SkillError("Bibliothèque 'mcp' non installée.")
        server = FastMCP(name)
        for tool_name, info in self.tools.items():
            fn = info.get("function")
            if callable(fn):
                server.add_tool(
                    fn,
                    name=tool_name,
                    description=info.get("description", "") or None,
                )
        return server

    def reload(self) -> list[str]:
        """Recharge les modules skills déjà importés."""
        for module_name in list(sys.modules):
            if module_name == "skills" or module_name.startswith("skills."):
                del sys.modules[module_name]
        return self.discover()
