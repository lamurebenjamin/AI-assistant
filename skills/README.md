# Guide de Création de Skills MCP pour l'Assistant IA

Ce document est le **guide de référence destiné aux IA et développeurs** pour concevoir, implémenter et tester de nouveaux **skills** basés sur le protocole standard **Model Context Protocol (MCP)** avec `FastMCP`.

---

## 1. Principes d'Architecture

Chaque skill réside dans son propre sous-dossier de `/skills` et remplit trois rôles simultanément :
1. **Outil LLM Local** : Exposable directement à `llama-server.exe` ou à tout modèle compatible OpenAI via `describe_for_llm()`.
2. **Serveur MCP Standard** : Déclaré via `FastMCP`, compatible avec les clients MCP externes (Claude Desktop, Cursor, Antigravity, etc.) via `scripts/run_mcp_server.py`.
3. **Composant UI Intégré** : Reconnu automatiquement par l'interface de l'assistant (menu déroulant `+` du compositeur Ctrl+9, icône vectorielle, actions directes).

---

## 2. Structure Standard d'un Dossier de Skill

Tout nouveau skill doit adopter l'arborescence suivante :

```text
skills/<nom_du_skill>/
├── __init__.py           # Fichier vide ou exports du package
├── skill.py              # Point d'entrée MCP + classe d'enregistrement
├── generator.py          # Logique métier pure (fonctions exécutables)
└── icon.svg              # Icône vectorielle (ou icon.png) pour l'UI
```

> [!IMPORTANT]
> Le nom du dossier doit être en minuscules, concis et sans accents (ex: `pdf`, `docx`, `excel`, `web_search`).

---

## 3. Règles d'Implémentation (`skill.py`)

### Règle 1 : Utiliser `core.mcp_compat`
Importez toujours `FastMCP` depuis `core.mcp_compat` pour assurer la compatibilité descendante et ascendante :
```python
from core.mcp_compat import FastMCP
```

### Règle 2 : Nommage des outils conforme à la norme MCP (SEP-986)
Les noms d'outils doivent être composés uniquement de caractères ASCII : `a-z`, `A-Z`, `0-9`, `_` (pas d'accents, espaces ou caractères spéciaux).
- **Correct** : `create_report`, `search_documents`, `export_csv`
- **Incorrect** : `créer_rapport`, `Détails`, `liste fichiers`

### Règle 3 : Typage strict obligatoire
`FastMCP` génère automatiquement le JSON Schema pour le LLM et MCP à partir des annotations de types Python.
- Utilisez `str`, `int`, `float`, `bool`, `list[...]`, `dict[str, Any]`, `Optional[...]`.
- N'omettez jamais les annotations sur les paramètres ni sur le type de retour.

### Règle 4 : Docstring explicite
Le LLM utilise la docstring de la fonction pour décider **quand et comment** invoquer l'outil.
- Résumez l'objectif dans la première ligne.
- Précisez les cas d'utilisation clés.
- Documentez les paramètres (`Args:`).

### Règle 5 : Écriture sécurisée des fichiers
Si le skill produit des fichiers (documents, images, exports) :
- Écrivez impérativement dans le dossier `output/` du projet :
  ```python
  project_root = Path(__file__).resolve().parents[2]
  output_dir = project_root / "output"
  output_dir.mkdir(parents=True, exist_ok=True)
  ```
- Protégez contre le *path traversal* en extrayant uniquement le nom de base :
  ```python
  safe_filename = Path(filename).name
  output_path = output_dir / safe_filename
  ```
- Retournez le **chemin absolu** sous forme de chaîne (`str(output_path.resolve())`).

### Règle 6 : Classe Wrapper pour l'intégration UI
Chaque `skill.py` doit définir une classe nommée `<NomCapitalisé>Skill` contenant au minimum :
- `name` : identifiant court en minuscules.
- `icon` : nom du fichier d'icône (ex: `"icon.svg"`).
- `mcp` : l'instance `FastMCP`.
- `get_tools()` : liste de rétrocompatibilité.

### Règle 7 : Pas de chemins en dur — Configuration Dynamique
Ne jamais intégrer de chemins absolus d'utilisateurs (`C:\Users\nom\...`) dans le code d'un skill :
- Les chemins de fichiers externes doivent être déclarés dans `config.json` sous la clé `skills.<nom_skill>` ou via des variables d'environnement.
- Exemple pour le skill FTNC :
  ```json
  "skills": {
    "ftnc": {
      "fichier_ftnc": "C:/Chemin/Vers/FTNC.xlsx",
      "feuille_ftnc": "Données consolidées",
      "fichier_suivi_euro": "C:/Chemin/Vers/Suivi des FTNC €uro.xlsx",
      "feuille_suivi_euro": "SUIVI"
    }
  }
  ```
- Les variables d'environnement `FTNC_FICHIER_PLANNER` et `FTNC_FICHIER_SUIVI_EURO` permettent également de surcharger ces chemins sans modifier `config.json`.

---

## 4. Modèle Complet de Skill (Template)

### Fichier `skills/mon_skill/generator.py` :
```python
"""Logique métier du skill mon_skill."""
from __future__ import annotations
from pathlib import Path
from typing import List


def generate_custom_report(filename: str, title: str, items: List[str]) -> str:
    """Génère un rapport dans output/ et retourne son chemin absolu."""
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"

    output_path = output_dir / safe_name
    content = f"# {title}\n\n" + "\n".join(f"- {item}" for item in items)
    output_path.write_text(content, encoding="utf-8")

    return str(output_path.resolve())
```

### Fichier `skills/mon_skill/skill.py` :
```python
"""Déclaration FastMCP pour mon_skill."""
from __future__ import annotations
from typing import List

from core.mcp_compat import FastMCP
from .generator import generate_custom_report

# 1. Instance FastMCP
mcp = FastMCP("mon_skill")


# 2. Outil MCP décoré avec typage complet
@mcp.tool(
    name="generate_custom_report",
    description=(
        "Génère un rapport texte structuré dans le dossier output du projet. "
        "À utiliser lorsque l'utilisateur demande une synthèse ou un rapport exporté."
    ),
)
def generate_custom_report_tool(filename: str, title: str, items: List[str]) -> str:
    """Crée un fichier de rapport à partir d'un titre et d'une liste d'éléments."""
    return generate_custom_report(filename=filename, title=title, items=items)


# 3. Classe d'enregistrement découverte par SkillManager
class MonSkillSkill:
    """Skill de démonstration pour l'Assistant IA."""

    name = "mon_skill"
    display_name = "Mon Skill"
    icon = "icon.svg"
    mcp = mcp

    def get_tools(self):
        """Rétrocompatibilité avec l'ancien inspecteur."""
        return [
            {
                "name": "generate_custom_report",
                "description": "Génère un rapport texte structuré dans le dossier output.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Nom du fichier"},
                        "title": {"type": "string", "description": "Titre du rapport"},
                        "items": {"type": "array", "items": {"type": "string"}, "description": "Éléments"},
                    },
                    "required": ["filename", "title", "items"],
                    "additionalProperties": False,
                },
                "function": generate_custom_report_tool,
            }
        ]
```

---

## 5. Guide des Tests Obligatoires

Pour garantir qu'un nouveau skill fonctionne sans faille, créez systématiquement un fichier de test unitaire :
`tests/test_skill_<nom_du_skill>.py`

### Checklist des 6 validations :

| Étape | Ce qui est testé | Méthode recommandée |
|-------|------------------|---------------------|
| **1. Découverte** | `SkillManager` détecte et charge le skill | `assertIn("mon_skill", sm.discover())` |
| **2. Outils MCP** | Tous les `@mcp.tool` sont enregistrés dans `sm.tools` | `assertIn("generate_custom_report", sm.tools)` |
| **3. Schéma LLM** | `sm.describe_for_llm()` produit un JSON Schema valide OpenAI | Vérifier `properties` et `required` |
| **4. Exécution unitaire** | `sm.execute_tool(...)` retourne le résultat attendu | Vérifier l'existence du fichier dans `output/` |
| **5. Serveur MCP** | L'outil est présent dans le serveur unifié `sm.get_unified_mcp_server()` | `server._tool_manager.get_tool(...)` |
| **6. Validation entrées** | Les valeurs aberrantes ou manquantes lèvent une erreur explicite | `assertRaises(ValueError)` |

### Modèle de Test Unitaire :
```python
"""Tests unitaires automatisés pour le skill mon_skill."""
import unittest
from pathlib import Path

from core.skill_manager import SkillManager


class MonSkillTests(unittest.TestCase):
    def setUp(self):
        self.manager = SkillManager()
        self.manager.discover()

    def test_01_skill_discovery(self):
        """Vérifie que le skill est bien découvert."""
        self.assertIn("mon_skill", self.manager.list_skills())
        self.assertIn("generate_custom_report", self.manager.tools)

    def test_02_llm_schema_conformance(self):
        """Vérifie la conformité du schéma envoyé à llama.cpp / OpenAI."""
        defs = self.manager.describe_for_llm()
        tool_def = next((d for d in defs if d["function"]["name"] == "generate_custom_report"), None)
        self.assertIsNotNone(tool_def, "L'outil doit être présent dans describe_for_llm")
        schema = tool_def["function"]["parameters"]
        self.assertIn("filename", schema["properties"])
        self.assertIn("title", schema["properties"])
        self.assertIn("items", schema["properties"])

    def test_03_execution(self):
        """Vérifie l'exécution directe de l'outil."""
        output_file = self.manager.execute_tool(
            "generate_custom_report",
            {
                "filename": "test_output.txt",
                "title": "Titre Test",
                "items": ["Point 1", "Point 2"],
            },
        )
        path = Path(output_file)
        self.assertTrue(path.is_file(), "Le fichier de sortie doit exister")
        content = path.read_text(encoding="utf-8")
        self.assertIn("Titre Test", content)
        self.assertIn("Point 1", content)
        # Nettoyage
        path.unlink(missing_ok=True)

    def test_04_mcp_unified_server(self):
        """Vérifie que le serveur MCP unifié intègre l'outil."""
        server = self.manager.get_unified_mcp_server("Test-Server")
        tools = server._tool_manager.list_tools()
        names = [t.name for t in tools]
        self.assertIn("generate_custom_report", names)


if __name__ == "__main__":
    unittest.main()
```

---

## 6. Commandes de Validation Rapide

Exécutez toujours ces commandes dans le terminal pour valider l'intégration :

```powershell
# 1. Vérifier la syntaxe et l'import
.\.venv\Scripts\python.exe -c "from skills.mon_skill.skill import mcp; print(mcp.name, 'OK')"

# 2. Lancer la suite de tests
.\.venv\Scripts\python.exe -m unittest discover tests

# 3. Tester l'exposition MCP globale
.\.venv\Scripts\python.exe scripts/run_mcp_server.py --help
```
