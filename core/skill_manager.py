"""Gestionnaire modulaire des skills de l'assistant IA."""
from __future__ import annotations

import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


class SkillError(Exception):
    """Erreur liée au chargement ou à l'exécution d'un skill."""


class SkillManager:
    """Découvre, enregistre et exécute les skills présents dans /skills."""

    def __init__(self, skills_directory: Optional[str | Path] = None):
        self.skills_directory = (
            Path(skills_directory).resolve()
            if skills_directory
            else Path(__file__).resolve().parent.parent / "skills"
        )
        self.skills: Dict[str, Any] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}

    def discover(self) -> List[str]:
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
            except Exception as exc:
                LOGGER.exception("Impossible de charger le skill '%s': %s", directory.name, exc)
        return loaded

    @staticmethod
    def _load_skill(package_name: str) -> Any:
        module = importlib.import_module(f"skills.{package_name}.skill")
        candidates = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ and obj.__name__.endswith("Skill"):
                candidates.append(obj)
        if not candidates:
            raise SkillError(f"Aucune classe *Skill dans skills.{package_name}.skill")
        if len(candidates) > 1:
            LOGGER.warning("Plusieurs classes *Skill dans %s ; utilisation de %s", module.__name__, candidates[0].__name__)
        return candidates[0]()

    @staticmethod
    def _skill_name(skill: Any) -> str:
        name = getattr(skill, "name", None)
        if not name:
            name = skill.__class__.__name__.removesuffix("Skill")
        return str(name).strip().lower()

    def _register_tools(self, skill_name: str, skill: Any) -> None:
        if not hasattr(skill, "get_tools"):
            return
        for tool in skill.get_tools() or []:
            if callable(tool):
                name = tool.__name__
                info = {"name": name, "skill": skill_name, "function": tool,
                        "description": inspect.getdoc(tool) or ""}
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
                raise SkillError(f"Outil déjà enregistré : {name}")
            self.tools[name] = info

    def list_skills(self) -> List[str]:
        return sorted(self.skills)

    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "skill": info["skill"], "description": info.get("description", "")}
            for name, info in sorted(self.tools.items())
        ]

    def get_skill(self, skill_name: str) -> Any:
        try:
            return self.skills[skill_name.strip().lower()]
        except KeyError as exc:
            raise SkillError(f"Skill inconnu : {skill_name}") from exc

    def get_tool(self, tool_name: str) -> Dict[str, Any]:
        try:
            return self.tools[tool_name.strip()]
        except KeyError as exc:
            raise SkillError(f"Outil inconnu : {tool_name}") from exc

    def execute(self, skill_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
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
            return function(**arguments)
        skill = self.get_skill(skill_name)
        if hasattr(skill, "execute"):
            return skill.execute(tool_name, arguments)
        raise SkillError(f"Impossible d'exécuter '{tool_name}'.")

    def execute_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Exécute directement un outil sans connaître son skill."""
        info = self.get_tool(tool_name)
        return self.execute(info["skill"], tool_name, arguments)

    def describe_for_llm(self) -> List[Dict[str, Any]]:
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

    def reload(self) -> List[str]:
        """Recharge les modules skills déjà importés."""
        for module_name in list(sys.modules):
            if module_name == "skills" or module_name.startswith("skills."):
                del sys.modules[module_name]
        return self.discover()
