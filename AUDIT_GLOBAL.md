# Audit global du projet

Date de la passe : **24/09/2026**  
Périmètre : maintenabilité Python, interface PySide6, design system, thèmes,
accessibilité, tests, CI, documentation et validation Windows.

Ce document consolide les constats de `MAINTAINABILITY_AUDIT.md`,
`UI_CONFORMANCE_AUDIT.md` et `UI_VISUAL_HARMONIZATION_AUDIT.md`. Les rapports
spécialisés restent conservés pour le détail historique et technique ; ce
document constitue la synthèse de référence.

## 1. Verdict exécutif

**État global : 🟡 maintenable et conforme sur le périmètre automatisé ; la
validation visuelle Windows native et la réduction de quelques contrôleurs UI
restent à finaliser.**

Les fondations sont solides :

- architecture séparée par domaines (`llm`, `documents`, `audio`, `tts`,
  `monitoring`, `ui`, `core`) ;
- tokens, icônes, helpers QSS et composants partagés centralisés ;
- façades publiques historiques conservées après les extractions ;
- authentification locale aléatoire de `llama-server` propagée aux requêtes
  concernées ;
- validation reproductible dans `.venv` et workflow CI Windows ;
- tests de contraste sémantique ajoutés pour les thèmes clair et sombre.

Les risques résiduels sont principalement :

1. contrôleurs UI encore volumineux ;
2. validation native Windows non observable en headless ;
3. violations Ruff existantes ;
4. vérification visuelle complète de l’accessibilité, des icônes, bordures et
   états avancés.

## 2. Résultats vérifiés

| Contrôle | Résultat | Interprétation |
|---|---:|---|
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | ✅ **108/108** | 108 réussites, 0 échec, 0 ignoré |
| `.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests` | ✅ | Compilation complète réussie |
| Compilation avec Python système | ✅ | Aucun échec de syntaxe observé |
| `git diff --check` sur le périmètre audité | ✅ | Aucun problème bloquant sur les fichiers contrôlés |
| Parité `THEME_DARK` / `THEME_LIGHT` | ✅ | Contrôle automatisé |
| Littéraux visuels hors sources autorisées | ✅ | Couleurs centralisées dans les tokens sur le périmètre testé |
| Contraste sémantique AA | ✅ | Textes principaux, liens, boutons primaires et focus |
| Contrôle des tailles de modules | ✅ | Seuil général de 500 lignes et allowlist contrôlée |
| Ruff | ✅ | 0 violation signalée ; 47 suppressions locales documentent des patterns comportementaux intentionnels |

Les messages audio, TTS et skill invalide visibles pendant les tests sont des
scénarios négatifs attendus et validés ; ils ne constituent pas des régressions.

## 3. Maintenabilité et architecture

### Points positifs

- Les responsabilités métier et UI sont réparties par domaine.
- `SettingsDialog` conserve son API publique ; la validation et la
  normalisation sont isolées dans
  [`settings_config.py`](src/ui/windows/settings_config.py).
- Les onglets Apparence et Ctrl+9 sont maintenant des classes autonomes
  [`AppearanceTab` et `Ctrl9Tab`](src/ui/windows/settings_tabs.py), tandis que
  `SettingsDialog` conserve ses attributs de contrôles historiques.
- La timeline d'outils est couverte par des tests d'intégration Qt avec des
  réponses complètes mockées (raisonnement, succès, erreur, résultats JSON et
  réponse finale), sans appel réseau, dans
  [`test_tool_timeline_integration.py`](tests/test_tool_timeline_integration.py).
- Le traitement des fichiers produits par les tools est isolé dans
  [`assistant_file_links.py`](src/ui/windows/assistant_file_links.py), avec
  façades historiques conservées.
- Les extractions de document, conversation, sources, réponses, composer,
  audio/TTS, timeline et styles QSS disposent de tests ciblés.
- `tool_call_widget.py` est repassé sous le seuil général de taille.
- Les contrats de configuration et plusieurs frontières LLM sont typés et
  documentés.

### Modules encore coûteux

| Module | Taille approximative | Action |
|---|---:|---|
| [`document_dialog.py`](src/ui/windows/document_dialog.py) | 1 125 lignes | Extraire seulement les responsabilités encore isolables |
| [`assistant_window.py`](src/ui/windows/assistant_window.py) | 1 190 lignes | Poursuivre l’extraction incrémentale |
| [`settings_dialog.py`](src/ui/windows/settings_dialog.py) | 758 lignes | Conserver la façade ; extractions d'onglets réalisées |
| [`stylesheet.py`](src/ui/stylesheet.py) | 680 lignes | Extraire uniquement les blocs réutilisables |
| [`document_conversation_renderer.py`](src/ui/windows/document_conversation_renderer.py) | 525 lignes | Surveiller avant nouvelle extraction |
| [`tool_call_step.py`](src/ui/widgets/tool_call_step.py) | 284 lignes | Pas d’extraction urgente |

Chaque extraction future doit :

1. isoler une responsabilité claire ;
2. ajouter les tests ciblés avant suppression de l’ancien code ;
3. préserver les façades publiques et les imports historiques ;
4. réduire l’allowlist de
   [`check_module_sizes.py`](scripts/check_module_sizes.py), jamais l’élargir.

## 4. Conformité UI et source unique de vérité

### Conforme

- couleurs, dimensions et états de thème centralisés dans
  [`design_tokens.py`](src/ui/design_tokens.py) ;
- icônes issues du registre de
  [`icons.py`](src/ui/icons.py) ;
- primitives QSS regroupées dans
  [`stylesheet.py`](src/ui/stylesheet.py) ;
- composants partagés pour headers, composer, statuts, skills et séparateurs ;
- `refresh_theme()` disponible sur les fenêtres persistantes couvertes ;
- tooltips, focus clavier, états hover/pressed/disabled et textes longs testés ;
- exceptions de styles documentées dans
  [`UI_STYLE_EXCEPTIONS.md`](UI_STYLE_EXCEPTIONS.md) ;
- règles de conception détaillées dans
  [`UI_DESIGN_RULES.md`](UI_DESIGN_RULES.md).

### Accessibilité automatisée

Les tests de [`test_ui_design_system.py`](tests/test_ui_design_system.py)
calculent les ratios WCAG pour :

- texte primaire, secondaire et liens sur le fond de page ;
- texte des boutons primaires dans les états normal, hover et pressed ;
- contraste minimal du focus dans les deux thèmes.

Les tokens faibles qui servent à des bordures, surfaces ou états désactivés ne
doivent pas être corrigés sans confirmer leur usage visuel réel.

## 5. Validation Windows native

La passe automatisée a été effectuée sous Windows 11 Professionnel, build
26200, avec un écran détecté et un DPI système de 96 (100 %).

✅ Validé automatiquement :

- suite headless ;
- compilation ;
- cohérence des thèmes et tokens ;
- contraste sémantique ;
- contrôle de taille et diff check.

🟡 À valider avec l’application visible :

- Acrylic et coins arrondis Windows 10/11 ;
- DPI 125 %, 150 % et 200 % ;
- déplacement entre plusieurs écrans ;
- tooltips sur fenêtres frameless/translucides ;
- tray, icônes et fallbacks ;
- raccourcis globaux ;
- fenêtres étroites et textes longs ;
- rendu clair/sombre des fenêtres principales ;
- contraste réel des icônes et bordures ;
- états `loading`, `success` et `error` sur toutes les surfaces.

La procédure détaillée est conservée dans
[`UI_WINDOWS_RELEASE_CHECKLIST.md`](UI_WINDOWS_RELEASE_CHECKLIST.md).

## 6. Qualité et dette restante

### 🟠 Priorité haute — contrôleurs UI

Réduire progressivement `document_dialog.py`, `assistant_window.py`,
`settings_dialog.py` et les responsabilités restantes de `stylesheet.py`.
Aucune refonte globale n’est nécessaire : les extractions doivent rester
incrémentales et compatibles.

### 🟡 Priorité moyenne — Ruff

Ruff ne signale désormais plus de violation. Les 47 suppressions locales
restantes documentent des patterns comportementaux intentionnels : captures
d'erreurs aux frontières audio/LLM/UI, closures de rendu Qt et blocs
`try/except` de nettoyage. Elles restent visibles dans le code et pourront être
remplacées par des exceptions plus précises lors d'une passe comportementale.

### 🟡 Priorité moyenne — accessibilité native

Compléter les tests visuels et clavier des fenêtres complètes, au-delà du seul
compositeur, puis joindre les captures prévues par la checklist de release.

### ⚪ Priorité basse — nettoyage documentaire

Maintenir les trois rapports spécialisés synchronisés tant qu’ils sont
référencés par des tickets ou des workflows. Toute nouvelle passe doit mettre
à jour ce rapport global en premier, puis les détails spécialisés si nécessaire.

## 7. Plan d’action priorisé

1. Exécuter la validation Windows interactive et archiver les preuves de
   release.
2. Réduire un contrôleur UI à la fois, avec test ciblé et façade conservée.
3. Traiter Ruff dans une passe indépendante et mesurable.
4. Étendre les contrôles d’accessibilité aux fenêtres complètes et aux
   tooltips.
5. Relancer la suite `.venv`, `compileall`, le contrôle de taille et les scans
   de tokens après chaque lot.

## 8. Commandes de référence

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests
.\.venv\Scripts\python.exe -m ruff check .
python scripts/check_module_sizes.py
git diff --check
```

## Documents sources

- [`MAINTAINABILITY_AUDIT.md`](MAINTAINABILITY_AUDIT.md)
- [`UI_CONFORMANCE_AUDIT.md`](UI_CONFORMANCE_AUDIT.md)
- [`UI_VISUAL_HARMONIZATION_AUDIT.md`](UI_VISUAL_HARMONIZATION_AUDIT.md)
- [`UI_WINDOWS_RELEASE_CHECKLIST.md`](UI_WINDOWS_RELEASE_CHECKLIST.md)
- [`UI_DESIGN_RULES.md`](UI_DESIGN_RULES.md)
- [`UI_STYLE_EXCEPTIONS.md`](UI_STYLE_EXCEPTIONS.md)
