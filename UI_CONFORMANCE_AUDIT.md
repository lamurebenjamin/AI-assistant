# Audit de conformité UI, règles et contrôles

Date de l'audit : 2026-09-22
Périmètre : interface PySide6, design system, thèmes, assets, Markdown et
contrôles de validation.
Méthode : lecture statique, recherches ciblées et exécution des contrôles
présents dans le dépôt et dans la CI Windows.

## Résumé exécutif

| Domaine | Évaluation | Conclusion |
| --- | --- | --- |
| Architecture visuelle | 🟢 Solide | Le design system est largement utilisé ; des styles locaux restent justifiés dans quelques surfaces complexes. |
| Thèmes clair/sombre | 🟢 Conforme | Les tokens sont paritaires et les fenêtres persistantes exposent `refresh_theme()`. |
| États interactifs | 🟢 Couvert | Les états principaux, le focus du compositeur et les tooltips sont testés. |
| Assets et icônes | 🟢 Conforme | Les skills déclarent leurs assets et disposent de fallbacks testés. |
| Tests automatisés | 🟢 Bonne couverture | 53 tests couvrent UI, configuration, skills, parsing LLM, serveur local, threads, contrats et contrôleurs UI. |
| Contrôles techniques | 🟢 Conforme | Compilation et contrôle `git diff --check` réussissent sur le périmètre audité. |

## Contrôles exécutés

| Contrôle | Résultat | Limite |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | ✅ 53 tests réussis | Couverture headless UI, configuration, skills, parsing LLM, serveur local, threads, contrats et contrôleurs UI. |
| `python -m unittest discover -s tests -v` | ✅ 53 tests réussis | Même suite headless validée avec Python système. |
| `.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests` | ✅ Réussi | Ne détecte pas les incohérences de thème ou de QSS. |
| `git diff --check -- src/ui tests README.md UI_DESIGN_RULES.md` | ✅ Réussi | Le périmètre UI audité est propre. |
| Recherche de couleurs dans les surfaces migrées | ✅ Aucune occurrence dans les fichiers ciblés | Les registres d'icônes et certains styles globaux conservent des valeurs intentionnelles mais non testées. |
| Inventaire des skills | ✅ `docx`, `excel`, `pdf`, `pptx`, `ftnc` possèdent un asset déclaré | Dimensions, lisibilité et contraste non automatisés. |

## Findings

### ✅ Résolu — Rafraîchissement dynamique du thème

Les fenêtres persistantes concernées disposent désormais d'une méthode
`refresh_theme()` et sont rafraîchies par le mécanisme global de thème.
Les tests vérifient la bascule sur les dialogues runtime, settings et
documentaires.

Les anciens risques liés aux tokens capturés statiquement sont donc clos pour
les fenêtres couvertes par les tests. La validation native Windows reste
manuelle pour Acrylic, DPI, tray et multi-écrans.

### ✅ Résolu — Couverture de tests UI et métier

Les douze suites de [`tests/`](tests/) contiennent désormais 53 tests headless
couvrant les widgets partagés, les états interactifs, les tooltips, le focus
clavier, les textes longs, le Markdown, les assets, la configuration, les
skills, le parsing LLM, le serveur local et le cycle de vie des threads.

### ✅ Amélioré — Styles locaux dans les fenêtres

**Preuves**

- [`settings_dialog.py`](src/ui/windows/settings_dialog.py) utilise désormais
  `qss_settings_emphasis()` pour les accents typographiques récurrents.
- [`document_dialog.py`](src/ui/windows/document_dialog.py) utilise des helpers
  pour la réponse, la navigation et les pièces jointes.
- [`tool_call_widget.py`](src/ui/widgets/tool_call_widget.py) et
  [`slash_command_popup.py`](src/ui/widgets/slash_command_popup.py) utilisent
  des helpers QSS pour leurs structures réutilisables.

**Impact**

Les règles de visualisation communes sont maintenant regroupées. Les styles
restants sont spécifiques au contenu dynamique, aux animations ou à une
composition locale et restent documentés dans
[`UI_STYLE_EXCEPTIONS.md`](UI_STYLE_EXCEPTIONS.md).

**Suivi**

La règle est désormais préventive : continuer à extraire uniquement les blocs
qui apparaissent sur plusieurs surfaces. Conserver les styles HTML générés
dynamiquement uniquement lorsqu'ils sont indispensables au rendu Qt rich-text.

### ✅ Résolu — Styles locaux dans les fenêtres complexes

Les styles locaux restants concernent principalement la composition spécifique
de [`settings_dialog.py`](src/ui/windows/settings_dialog.py),
[`document_dialog.py`](src/ui/windows/document_dialog.py) et
[`runtime_info_dialog.py`](src/ui/windows/runtime_info_dialog.py). Ils utilisent
désormais les tokens ; le risque restant est la duplication de structure QSS,
pas une divergence de palette.

### ⚪ LOW — Validation Windows native

Les scénarios Acrylic, DPI, tray, raccourcis globaux, tooltips frameless et
multi-écrans ne sont pas fiables en headless. Ils doivent rester dans la
checklist manuelle de release Windows.

## Matrice règles → contrôles

| Règle | Preuve actuelle | Contrôle automatisé recommandé | Contrôle manuel |
| --- | --- | --- | --- |
| Une couleur a une source unique | Recherche de littéraux | Scan des fenêtres/widgets hors exceptions documentées | Vérification visuelle des états |
| Tokens présents dans les deux thèmes | Test existant | Parité exacte des clés + génération QSS dans les deux thèmes | Bascule à chaud |
| États normal/hover/pressed/focus/disabled | QSS partiel | Tests Qt d'état et présence des sélecteurs | Navigation souris/clavier |
| Boutons icon-only avec tooltip | Plusieurs tooltips présents | Test de chaque bouton public | Vérification lisibilité du tooltip |
| Icônes avec fallback | Helpers existants | Asset présent/absent + formats SVG/PNG/ICO | Contraste et netteté DPI |
| Layouts et dimensions sémantiques | Tokens partiels | Scan des dimensions interdites + snapshot des tailles clés | Largeur étroite et texte long |
| Markdown commun | Helper centralisé | Cas listes, code, liens, sources, erreurs | Vérification rich-text Qt |
| Changement de thème dynamique | `apply_app_theme()` + `refresh_theme()` | Tests des fenêtres persistantes | Windows 10/11 + Acrylic |
| Contrôle du dépôt | Compilation réussie | unittest, compileall, diff check, lint statique | Revue visuelle de release |

## Plan de corrections priorisé

### Lot A — Renforcer les règles statiques — ✅ réalisé

1. Scanner les littéraux visuels hors fichiers autorisés. **Réalisé pour hex,
   rgba et dimensions fixes des widgets partagés.**
2. Vérifier la parité des tokens et des clés d'icônes. **Réalisé pour les
   tokens et les assets de skills.**
3. Vérifier la présence et les extensions des assets de skills. **Réalisé.**
4. Ajouter une liste d'exceptions versionnée. **Réalisé dans
   `UI_STYLE_EXCEPTIONS.md`.**

### Lot B — Accessibilité et revue visuelle

1. Définir le comportement focus des boutons custom.
2. Vérifier les contrastes par thème.
3. Tester DPI, Acrylic, tray, raccourci et fenêtres étroites sur Windows.

## Conclusion

Le socle visuel est conforme sur le périmètre automatisé. Les contrôles
couvrent les composants principaux, le changement de thème, les tokens, les
états et les dimensions partagées. Le seul contrôle restant est la validation
native Windows, sans bloquer les évolutions courantes si les règles de
[`UI_DESIGN_RULES.md`](UI_DESIGN_RULES.md) sont respectées.
