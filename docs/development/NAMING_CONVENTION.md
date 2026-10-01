# Convention de structure et de nommage

Ce document définit les règles applicables aux nouveaux fichiers et précise
les exceptions historiques conservées pour préserver les imports existants.

## 1. Règle générale

- Utiliser des noms ASCII, explicites et stables.
- Préférer `snake_case` pour les fichiers Python, les packages, les scripts et
  les tests.
- Éviter les abréviations non documentées, les noms génériques (`utils.py`,
  `helpers.py`) et les suffixes redondants.
- Le nom d'un fichier doit décrire sa responsabilité principale, pas son
  appelant.
- Ne pas renommer un module public sans rechercher et mettre à jour tous ses
  imports, tests et références documentaires.

## 2. Arborescence

```text
src/<domaine>/              # code applicatif par responsabilité
src/ui/widgets/             # composants réutilisables
src/ui/windows/             # fenêtres, contrôleurs et renderers de fenêtres
tests/                      # tests unittest
skills/<skill>/             # un dossier minuscule par skill MCP
scripts/                    # outils de maintenance et validation
```

Les packages Python doivent rester en minuscules et comporter un
`__init__.py` lorsqu'ils sont importés comme packages explicites.

## 3. Python

| Élément | Convention | Exemple |
| --- | --- | --- |
| Module | `snake_case.py` | `server_manager.py` |
| Package | minuscules | `documents/` |
| Classe | `PascalCase` | `DocumentDialog` |
| Fonction ou méthode | `snake_case` | `parse_response` |
| Constante | `UPPER_SNAKE_CASE` | `DEFAULT_CONFIG` |
| Test | `test_<module>.py` | `test_server_manager.py` |
| Classe de test | `<Sujet>Tests` | `ServerManagerTests` |

Un fichier contenant plusieurs implémentations liées peut employer un nom
pluriel, par exemple `hotkey_managers.py`, lorsqu'il regroupe réellement
plusieurs classes du même domaine. Cette exception est conservée dans le code
existant ; les nouveaux fichiers doivent préférer un nom singulier décrivant
leur responsabilité lorsqu'une seule classe domine.

Les suffixes ont un sens précis :

- `_manager` : cycle de vie, découverte ou orchestration d'une ressource ;
- `_controller` : coordination d'une fenêtre ou d'un flux UI ;
- `_renderer` : transformation de données en rendu ;
- `_thread` : travail exécuté dans un thread ;
- `_dialog`, `_window` : surface UI correspondante ;
- `_parser`, `_builder`, `_formatter` : transformation spécialisée.

## 4. Documentation et configuration

- `README.md` est le point d'entrée utilisateur.
- `AGENTS.md` contient les instructions de développement pour les agents.
- `docs/development/NAMING_CONVENTION.md` contient cette convention.
- Les audits sont regroupés dans `docs/audits/` et utilisent
  `UPPER_SNAKE_CASE.md` (`AUDIT_GLOBAL.md`, etc.). Les règles UI sont dans
  `docs/ui/` et la checklist de validation dans `docs/release/`.
- Les guides propres à un skill utilisent `instructions.md` dans le dossier
  du skill.
- Les fichiers de configuration restent en minuscules (`config.json`,
  `requirements-dev.txt`).

Les documents historiques ne doivent pas être renommés uniquement pour
uniformiser la casse : leurs liens peuvent être référencés par des tickets,
des scripts ou des outils externes. Toute migration de documentation doit
inclure une recherche des liens et une mise à jour atomique des références.

## 5. Skills MCP

- Le dossier du skill est court, en minuscules et sans accents.
- Le point d'entrée est `skill.py`.
- La logique métier pure va dans `generator.py` ou dans un module portant un
  nom métier explicite.
- Les instructions destinées au modèle sont dans `instructions.md`.
- Les tests suivent `tests/test_skill_<nom_du_skill>.py` lorsqu'un test dédié
  est nécessaire.

## 6. Procédure de renommage

Avant de renommer un fichier :

1. rechercher le chemin, le module et les symboles dans `src/`, `core/`,
   `skills/`, `tests/`, les scripts et les documents Markdown ;
2. vérifier les imports dynamiques, les chemins construits et les tests ;
3. renommer le fichier avec Git, puis mettre à jour les imports et les liens ;
4. exécuter les tests ciblés, la suite complète et `git diff --check` ;
5. documenter une éventuelle compatibilité temporaire si l'ancien import doit
   rester disponible.

## 7. État actuel

La structure actuelle respecte déjà cette convention dans l'ensemble. Aucun
renommage massif n'est recommandé : les noms existants sont conservés lorsque
leur changement n'apporterait pas de gain fonctionnel et risquerait de casser
des imports ou des références externes.
