# Audit de maintenabilité et de facilité de mise à jour

Date : 2026-09-22 — passe post-commit
Périmètre : architecture Python, modules UI, configuration, skills,
dépendances, tests, documentation et contrôles de maintenance.

## Verdict

**État global : 🟡 maintenable, mais encore coûteux à faire évoluer sur les
surfaces UI complexes.**

L'architecture est correctement découpée par domaine (`llm`, `documents`,
`audio`, `tts`, `monitoring`, `ui`, `core`). Les tokens, helpers QSS,
composants partagés et tests UI constituent de bonnes bases.

Les coûts de maintenance restent concentrés dans :

- [`document_dialog.py`](src/ui/windows/document_dialog.py) : 1 125 lignes ;
- [`document_conversation_renderer.py`](src/ui/windows/document_conversation_renderer.py) : 525 lignes ;
- [`document_source_renderer.py`](src/ui/windows/document_source_renderer.py) : 82 lignes ;
- [`assistant_window.py`](src/ui/windows/assistant_window.py) : 1 218 lignes ;
- [`assistant_response_renderer.py`](src/ui/windows/assistant_response_renderer.py) : 91 lignes ;
- [`settings_dialog.py`](src/ui/windows/settings_dialog.py) : 736 lignes ;
- [`stylesheet.py`](src/ui/stylesheet.py) : 680 lignes ;
- [`tool_call_widget.py`](src/ui/widgets/tool_call_widget.py) : 361 lignes ;
- [`tool_call_step.py`](src/ui/widgets/tool_call_step.py) : 284 lignes ;
- [`stylesheet_document.py`](src/ui/stylesheet_document.py) : 200 lignes ;
- [`timeline_header.py`](src/ui/widgets/timeline_header.py) : 214 lignes.

Ces modules mélangent encore orchestration, layout, rendu, événements et
logique de contenu. Une modification visuelle ou un changement de flux métier
nécessite donc souvent de parcourir un fichier très large.

## Contrôles effectués

| Contrôle | Résultat |
| --- | --- |
| Tests complets avec `.venv` | ✅ 55/55 |
| Tests complets avec Python système | ✅ 55/55 |
| Compilation avec les deux interpréteurs | ✅ |
| `git diff --check` sur le périmètre audité | ✅ |
| Scan des couleurs hex/`rgba` dans l'UI | ✅ Centralisé dans les tokens |
| Inventaire des modules | ✅ Découpage par domaine présent |
| Inventaire de la taille des fichiers | ⚠️ Trois modules dépassent 700 lignes |
| Contrôle automatique de taille | ✅ `scripts/check_module_sizes.py` avec seuil par défaut et allowlist documentée |
| Rapport de couverture CI | ✅ `coverage report --show-missing` dans le workflow Windows |

Le dernier commit applicatif est `e408f1a`. Le worktree contient encore des
modifications volontairement hors de ce commit dans `src/llm/` et `skills/`,
ainsi que de nouveaux assets/éléments du skill FTNC ; ils doivent être traités
dans une passe séparée pour conserver des commits ciblés.

## Nettoyage effectué le 22/09/2026

- Suppression du log local généré `llama-server.log`.
- Nettoyage des fichiers de démonstration générés dans `output/`, dossier
  conservé et ignoré car les skills l'utilisent comme destination runtime.
- Les anciens fichiers `scratch/` déjà supprimés du worktree ne sont pas
  restaurés.
- Les modèles locaux, DLL et exécutables nécessaires à l'installation Windows
  sont conservés : ils sont ignorés par Git mais ne sont pas des fichiers
  inutilisés fonctionnellement.
- Les rapports d'audit, règles UI et checklists sont conservés car ils sont
  référencés depuis le README et font partie de la documentation de maintenance.

## Points positifs

### Architecture par responsabilité

Les domaines principaux sont séparés et les fenêtres UI ne portent plus seules
toute la logique du projet. [`SkillManager`](core/skill_manager.py) expose une
API claire de découverte, description et exécution. Le chargement de
configuration est également isolé dans [`manager.py`](src/config/manager.py).

### Design system exploitable

Les règles de mise à jour visuelle sont documentées dans
[`UI_DESIGN_RULES.md`](UI_DESIGN_RULES.md), les exceptions dans
[`UI_STYLE_EXCEPTIONS.md`](UI_STYLE_EXCEPTIONS.md), et les primitives QSS dans
[`stylesheet.py`](src/ui/stylesheet.py).

### Validation reproductible

La suite `.venv` et l'interpréteur Python système passent chacun 55 tests. Les contrôles
statiques empêchent déjà plusieurs régressions : couleurs hors tokens,
`rgba(...)` dispersés, dimensions fixes littérales dans les widgets partagés et
helpers QSS non couverts.

## Écarts et risques de maintenance

### 🟠 HIGH résiduel — Modules UI encore volumineux

Les fenêtres principales regroupent trop de responsabilités :

- construction des widgets ;
- styles et rafraîchissement de thème ;
- gestion de l'historique ;
- rendu des pièces jointes ;
- navigation entre tours ;
- génération de menus ;
- gestion d'événements et d'états.

**Impact :** risque élevé de régression lors d'une modification locale,
difficulté de revue et temps d'onboarding élevé.

**Action restante :** poursuivre l'extraction par responsabilité sur la fenêtre
de paramètres encore volumineuse :

1. `settings_dialog.py` : validateurs de configuration résiduels.

Chaque extraction doit conserver l'API publique de la fenêtre et ajouter des
tests ciblés avant suppression de l'ancien code.

**Avancement :** la responsabilité attachment preview/page range a été extraite
dans [`document_attachment_preview.py`](src/ui/widgets/document_attachment_preview.py)
et la construction des onglets de configuration dans
[`settings_tabs.py`](src/ui/windows/settings_tabs.py).
`DocumentDialog` conserve ses méthodes et attributs publics par composition et
délégation, tandis que `SettingsDialog` conserve les contrôles publics
construits par le builder. La conversation/navigation des sources est maintenant
déléguée à [`conversation_controller.py`](src/ui/windows/conversation_controller.py)
et l'orchestration audio/TTS/tray/statut à
[`assistant_orchestration.py`](src/ui/controllers/assistant_orchestration.py).
Les contrôleurs conservent les façades publiques des fenêtres.
Les gros composants transverses ont également été découpés : les règles QSS
documentaires sont dans
[`stylesheet_document.py`](src/ui/stylesheet_document.py), tandis que les
primitives d'en-tête de timeline sont dans
[`timeline_header.py`](src/ui/widgets/timeline_header.py). Les imports publics
historiques restent réexportés. Le rendu d'une étape d'outil est maintenant
isolé dans [`tool_call_step.py`](src/ui/widgets/tool_call_step.py), ce qui
laisse au widget de groupe uniquement l'orchestration de la timeline.
Le cycle de réponse (streaming, timeline d'outils, finalisation et erreurs) est
également délégué à
[`document_response_controller.py`](src/ui/windows/document_response_controller.py),
avec deux tests ciblés couvrant la création du tour et les fragments SSE.
Le rendu conversationnel, la gestion du viewport et les captures de sources
sont maintenant délégués à
[`document_conversation_renderer.py`](src/ui/windows/document_conversation_renderer.py)
et [`document_source_renderer.py`](src/ui/windows/document_source_renderer.py).
La fenêtre conserve ses façades historiques pour les appels internes et
externes.
L'orchestration du compositeur (envoi, historique et microphone) est maintenant
déléguée à
[`document_composer_controller.py`](src/ui/windows/document_composer_controller.py),
avec deux tests ciblés sur l'envoi et la navigation de l'historique.
Le rendu HTML de réponse, l'animation d'attente et le flush du streaming de
`AssistantWindow` sont maintenant délégués à
[`assistant_response_renderer.py`](src/ui/windows/assistant_response_renderer.py),
avec deux tests ciblés. Les raccourcis restent exposés par la façade et leur
orchestration audio/tray est déjà centralisée dans
[`assistant_orchestration.py`](src/ui/controllers/assistant_orchestration.py).

### ✅ Résolu — Couverture de tests répartie

La couverture est maintenant répartie entre douze fichiers de tests, dont la
suite UI historique. Les risques métier sont désormais vérifiés explicitement
pour :

- migrations de configuration et valeurs invalides ;
- déduplication des arguments llama-server ;
- découverte/rechargement/exécution des skills ;
- parsing des réponses LLM et flux SSE ;
- arrêt propre des threads audio/TTS/documents ;
- erreurs réseau et disponibilité du serveur.

Les suites indépendantes suivantes sont maintenant présentes :

- `tests/test_config_manager.py` ;
- `tests/test_skill_manager.py` ;
- `tests/test_response_parser.py` ;
- `tests/test_server_manager.py` ;
- `tests/test_thread_lifecycle.py`.

Les tests restent sans matériel ni serveur réel, avec répertoires temporaires,
fixtures et adapters simulés. Les 53 tests passent dans `.venv`.
Le dernier rapport `coverage` couvre 35 % de `src` et `core` ; il est publié
comme indicateur de progression dans la CI, sans seuil bloquant tant que les
surfaces UI natives et les dépendances matérielles ne sont pas isolées.

### ✅ Résolu — Dépendances séparées par usage

Les dépendances sont maintenant séparées par profil. Le socle commun est dans
[`requirements.txt`](requirements.txt), l'interface et l'audio dans
[`requirements-ui.txt`](requirements-ui.txt), les skills dans
[`requirements-skills.txt`](requirements-skills.txt), et les outils de
validation dans [`requirements-dev.txt`](requirements-dev.txt).

Les profils suivants sont en place :

- `requirements-dev.txt` compose les trois profils pour une validation
  complète et ajoute Ruff ;
- `onnxruntime-gpu==1.19.2` reste explicitement épinglé dans le profil UI.

### ✅ Résolu — Documentation d'architecture

Le [`README.md`](README.md) décrit désormais l'architecture par responsabilités
sans annoncer une taille moyenne irréaliste. L'arborescence inclut les tokens,
les helpers QSS, les widgets partagés et les builders récemment extraits ; les
rapports spécialisés sont liés depuis la section UI.

Le README sert de guide d'entrée qualitatif et renvoie aux documents
spécialisés d'UI, de conformité, de release Windows et de maintenabilité. Les
références obsolètes vers `Assistant.pyw` et `UI_AUDIT_REPORT.md` ont été
supprimées.

### ✅ Amélioré — Contrats publics

Les modules possèdent peu de documentation sur leurs contrats d'entrée/sortie,
les signaux Qt, les états et les erreurs attendues. Cela concerne surtout les
threads, le client LLM et les fenêtres qui manipulent des dictionnaires métier.

**Mise en œuvre :**

- les structures principales de configuration sont décrites par des
  `TypedDict` dans [`schema.py`](src/config/schema.py) ;
- les outils de skills disposent d'un contrat `ToolDefinition` et l'exception
  métier `SkillError` est documentée ;
- les signaux, états terminaux, opérations d'arrêt et erreurs attendues sont
  documentés dans les threads audio, TTS, LLM et documentaire ;
- les parseurs et le gestionnaire `llama-server` documentent leurs tuples de
  sortie et leurs erreurs explicites.

Les dictionnaires de payload LLM restent volontairement souples car leur forme
est imposée par la compatibilité OpenAI/llama.cpp ; les points d'entrée stables
sont annotés avec `Dict[str, Any]` plutôt que de masquer les extensions
possibles par des casts.

### ✅ Résolu — Contrôles qualité automatisés

Un workflow Windows versionné est maintenant présent dans
[`.github/workflows/quality.yml`](.github/workflows/quality.yml). Il crée
`.venv`, installe `requirements-dev.txt`, puis exécute automatiquement :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests
git diff --check
```

Le job utilise `windows-latest`, Python 3.12, le cache pip et
`QT_QPA_PLATFORM=offscreen` pour conserver les tests Qt sans matériel ni
affichage interactif.

## Règles de maintenance recommandées

1. Un fichier métier ou UI nouveau doit rester sous 500 lignes ; au-delà,
   extraire une responsabilité.
2. Toute extraction doit préserver l'API publique et être accompagnée d'un
   test ciblé.
3. Les dictionnaires partagés entre modules doivent devenir des dataclasses ou
   `TypedDict`.
4. Toute dépendance ajoutée doit être classée par usage et documentée.
5. Toute fonction qui gère une ressource (thread, processus, fichier,
   périphérique) doit documenter son cycle de vie et son nettoyage.
6. Les erreurs doivent être journalisées avec leur contexte et ne pas être
   transformées en succès silencieux.
7. Les rapports d'audit doivent indiquer la date, la commande exacte et le
   nombre de tests obtenu.

## Roadmap priorisée

### Priorité 1 — Réduire le risque UI

- ✅ extraire les pièces jointes et aperçus PDF de `document_dialog.py` ;
- ✅ extraire le rendu conversationnel et la navigation des sources de
  `document_dialog.py` ;
- ✅ extraire le cycle de réponse et le streaming de `document_dialog.py` ;
- ✅ extraire l'orchestration du compositeur, de l'historique et du microphone ;
- ✅ extraire le rendu conversationnel, le viewport et les sources ;
- ✅ extraire les règles QSS documentaires de `stylesheet.py` ;
- ✅ extraire les primitives de header de `tool_call_widget.py` ;
- ✅ extraire le rendu des étapes individuelles de `tool_call_widget.py` ;
- ✅ extraire l'orchestration audio/TTS, tray et statut de
  `assistant_window.py` ;
- ✅ extraire le rendu HTML et le streaming de `assistant_window.py` ;
- ✅ ajouter des tests ciblés avant chaque extraction ;
- poursuivre ensuite l'extraction des validateurs de `settings_dialog.py`.

### Priorité 2 — Formaliser les contrats

- ✅ typer les frontières `LlmMessage`, `LlmResponse` et `DocumentTurn` sans
  rigidifier le format compatible OpenAI/llama.cpp ;
- documenter les contrats des fenêtres qui consomment encore des dictionnaires
  métier implicites.

### Priorité 3 — Automatiser la qualité

- ✅ CI minimale Windows ajoutée dans
  [`.github/workflows/quality.yml`](.github/workflows/quality.yml) ;
- ✅ ajouter un contrôle automatique de taille des modules ;
- ✅ publier les résultats de couverture dans la CI ;
- conserver la validation native Windows comme étape manuelle de release.

Le contrôle de taille est désormais exécuté dans la CI avec un seuil par défaut
de 500 lignes. Les orchestrateurs UI déjà identifiés disposent d'une limite
transitoire explicitement listée dans `scripts/check_module_sizes.py`; la limite
de `document_dialog.py` a été réduite à 1 800 lignes et le module est désormais
bien en dessous de cette limite après les extractions conversationnelles. Chaque
extraction doit réduire cette allowlist plutôt que l'étendre.

## Conclusion

Le projet est suffisamment modulaire pour continuer à évoluer. Les principaux
risques historiques sont traités par les tests indépendants, les profils de
dépendances, les contrats typés et la CI. L'effort restant doit se concentrer
sur la réduction des gros contrôleurs UI, avec une extraction incrémentale,
préservant l'API publique et accompagnée d'un test ciblé.
