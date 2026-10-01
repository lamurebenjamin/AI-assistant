# Instructions de développement pour les agents IA

Ce fichier est la référence opérationnelle pour toute intervention d'un LLM
ou d'un agent de programmation dans ce dépôt.

## 1. Principes de travail

1. **Comprendre avant de modifier** : inspecter les fichiers concernés, leurs
   appelants, les tests associés et la documentation liée avant toute édition.
2. **Modifier au plus près du besoin** : privilégier les changements ciblés,
   réutiliser les helpers existants et ne pas corriger les problèmes
   préexistants sans rapport avec la demande.
3. **Préserver les contrats** : conserver les API publiques, les comportements
   utilisateur, la compatibilité Windows et les formats persistés, sauf
   demande explicite.
4. **Une seule source de vérité** : ne pas dupliquer une constante, une icône,
   un token, un schéma ou une règle déjà centralisé.
5. **Échecs explicites** : ne pas masquer une exception, retourner un succès
   fictif ou utiliser un fallback silencieux. Utiliser le logging et les
   notifications déjà présents dans le projet.
6. **Pas de secrets ni de chemins machine** : ne jamais ajouter de secret,
   identifiant privé ou chemin absolu dépendant d'un utilisateur.

## 2. Méthode obligatoire

### Avant l'édition

- Vérifier l'état Git et ne jamais écraser les modifications existantes.
- Rechercher les implémentations et tests similaires avant d'ajouter une
  fonction ou un composant.
- Identifier le contrat à préserver : entrées, sorties, exceptions, signaux,
  fichiers produits et effets de bord.
- Définir le test de non-régression correspondant au bug ou à la fonctionnalité.

### Pendant l'édition

- Respecter le typage et les conventions de nommage existants.
- Documenter les arguments, retours et exceptions des nouvelles API publiques.
- Garder les opérations de fichiers, processus, threads et ressources
  explicitement fermables.
- Valider toute entrée provenant de l'utilisateur, du LLM ou d'une
  configuration avant de l'utiliser.
- Mettre à jour la documentation directement concernée par le changement.

### Après l'édition

- Examiner le diff et vérifier qu'il ne contient ni fichier temporaire, ni
  donnée sensible, ni changement hors périmètre.
- Exécuter les tests ciblés, puis la validation complète lorsque du code a été
  modifié.
- Vérifier le résultat réel de la commande : ne pas déclarer une validation
  réussie sur la seule base de son lancement.
- Résumer la cause racine, la solution et les validations effectuées.

Les règles détaillées de structure et de nommage sont centralisées dans
[`NAMING_CONVENTION.md`](docs/development/NAMING_CONVENTION.md). Avant tout renommage, suivre sa
procédure de recherche des imports, références dynamiques et liens.

## 3. Tests et validation

Toute correction de bug doit inclure un test qui reproduit le cas défaillant.
Toute nouvelle fonctionnalité, skill, fenêtre ou composant doit inclure les
tests adaptés. Une nouvelle vue ou boîte de dialogue doit également vérifier
qu'elle ne laisse pas d'état fantôme ou de superposition indésirable.

Commandes de référence depuis la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/check_module_sizes.py
git diff --check
```

Adapter la validation au périmètre :

- documentation seule : relire le rendu et les liens ;
- logique Python : test ciblé, puis suite `unittest` complète ;
- UI : tests ciblés, suite complète et contrôle des règles UI ;
- dépendance, configuration ou processus : tests concernés, compilation et
  vérification de démarrage si elle est disponible.

Une validation impossible ou en échec doit être signalée avec la commande et
la cause ; elle ne doit pas être contournée.

## 4. Source unique de vérité pour l'interface

### Icônes

- Toutes les icônes doivent être déclarées dans le registre `_SVG` de
  [`src/ui/icons.py`](src/ui/icons.py).
- Les boutons doivent utiliser `ICONS` ou `ICONS_DARK`.
- Ne pas dessiner d'icône ad hoc avec `QPainter`.
- Vérifier [`tests/test_icon_consistency.py`](tests/test_icon_consistency.py).

### Design system

- Dans les composants UI, utiliser les tokens de
  [`src/ui/design_tokens.py`](src/ui/design_tokens.py) pour les couleurs,
  dimensions, tailles de boutons et tailles d'icônes.
- Ne pas introduire de couleur hexadécimale ou de dimension arbitraire quand
  un token existe déjà.
- Toute exception doit être justifiée dans
  [`UI_STYLE_EXCEPTIONS.md`](docs/ui/UI_STYLE_EXCEPTIONS.md).

### Tooltips et onglets

- Installer les tooltips exclusivement avec
  `install_tooltip(widget, text)` depuis `src/ui/fluent_compat.py`.
- Utiliser `QStackedWidget` avec la synchronisation
  `Pivot.currentItemChanged`; ne pas empiler manuellement plusieurs pages
  visibles.

## 5. Sécurité, fichiers et processus

- Construire les chemins avec `Path` et la configuration du projet ; ne jamais
  coder un chemin utilisateur en dur.
- Pour un nom de fichier fourni par l'extérieur, neutraliser le traversal
  avec `Path(filename).name`, vérifier l'extension et l'emplacement autorisé.
- Pour les skills, produire les fichiers dans `output/` sauf contrat contraire
  documenté.
- Nettoyer les fichiers temporaires et fermer les fichiers, flux audio,
  processus et threads ; utiliser les mécanismes de shutdown existants.
- Nettoyer et valider les arguments transmis à `llama-server`, `nvidia-smi`
  ou à tout autre processus externe.
- Ne jamais journaliser de secret, contenu privé ou jeton d'authentification.

## 6. Skills MCP

Un skill doit suivre le guide de [`skills/README.md`](skills/README.md) :

- dossier dédié sous `skills/`, nom ASCII en minuscules ;
- `FastMCP` importé depuis `core.mcp_compat` ;
- outils nommés en ASCII, typés et documentés ;
- classe wrapper découverte par `SkillManager` ;
- logique métier testable séparément de l'intégration MCP ;
- validation des entrées et protection contre le *path traversal*.

Si une commande, une dépendance, un skill ou une configuration change, mettre à
jour [`README.md`](README.md), [`skills/README.md`](skills/README.md) et les
audits concernés.

## 7. Documentation et traçabilité

Mettre à jour les docstrings, annotations et documents directement affectés.
Pour une modification d'architecture ou d'interface, vérifier notamment :

- [`MAINTAINABILITY_AUDIT.md`](docs/audits/MAINTAINABILITY_AUDIT.md) ;
- [`UI_DESIGN_RULES.md`](docs/ui/UI_DESIGN_RULES.md) ;
- les audits UI ou de release concernés.

La réponse finale doit indiquer :

1. la cause racine identifiée ;
2. les fichiers et comportements modifiés ;
3. les tests et commandes exécutés ;
4. toute limite ou validation impossible.

## 8. Checklist de clôture

- [ ] Le changement répond exactement à la demande et reste dans son périmètre.
- [ ] Le bug ou la fonctionnalité possède le test approprié.
- [ ] Les sources uniques (icônes, tokens, tooltips, schémas) sont respectées.
- [ ] Les ressources et fichiers temporaires sont correctement gérés.
- [ ] Aucun secret ni chemin machine n'a été ajouté.
- [ ] La documentation concernée est à jour.
- [ ] Les validations pertinentes sont passées, ou leurs échecs sont documentés.
- [ ] Le diff final a été relu avec `git diff --check`.
