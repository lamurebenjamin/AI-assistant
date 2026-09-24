# Audit d'harmonisation visuelle

Date : 2026-09-24
Périmètre : `src/ui/`, rendu Markdown, tokens, QSS, thèmes, états
interactifs, assets de skills et tests associés.

## Verdict

**État global : 🟢 conforme sur le périmètre automatisé, 🟡 validation native
Windows restant manuelle.**

Le design system est maintenant réellement utilisé : tokens paritaires
clair/sombre, helpers QSS, composants partagés (`WindowChrome`, `ComposerBar`,
`StatusLabel`, `SkillTag`, `HairlineSeparator`) et API `refresh_theme()`.
La couverture de tests a fortement progressé : **108 tests passent** avec
l'interpréteur du projet (`.venv`).

Les styles locaux restants sont documentés et limités au contenu dynamique, aux
animations et aux compositions spécifiques. Le seul écart significatif restant
est la validation visuelle Windows native, qui nécessite un poste graphique
réel.

## Contrôles réalisés

| Contrôle | Résultat | Commentaire |
| --- | --- | --- |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | ✅ 108/108 | UI, configuration, skills, parsing LLM, serveur local, authentification locale, threads, contrats et contrôleurs UI. |
| `.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests` | ✅ | Aucun échec de compilation. |
| `python -m compileall -q src core skills main.pyw tests` | ✅ | Aucun échec avec Python système. |
| `git diff --check -- src/ui tests README.md requirements.txt UI_*.md` | ✅ | Le périmètre audité est propre. |
| Parité des clés `THEME_DARK` / `THEME_LIGHT` | ✅ | Test automatisé. |
| Littéraux hex hors `design_tokens.py` | ✅ | Test automatisé. |
| `.venv\Scripts\python.exe -m ruff check .` | ⚠️ Échec | Violations de style Ruff ; aucun test fonctionnel en échec. |

## Points positifs vérifiés

### Sources de vérité visuelle

- Les couleurs sont centralisées dans
  [`design_tokens.py`](src/ui/design_tokens.py).
- Les primitives QSS sont regroupées dans
  [`stylesheet.py`](src/ui/stylesheet.py).
- Les icônes sont gérées par
  [`icons.py`](src/ui/icons.py), avec fallbacks et variantes de thème.
- Les composants partagés sont présents dans
  [`src/ui/widgets/`](src/ui/widgets/).
- Les règles sont documentées dans
  [`UI_DESIGN_RULES.md`](UI_DESIGN_RULES.md).

### Cohérence des écrans

Les composants suivants fournissent une base cohérente :

- [`WindowChrome`](src/ui/widgets/window_chrome.py) pour les headers ;
- [`ComposerBar`](src/ui/widgets/composer_bar.py) pour la saisie ;
- [`StatusLabel`](src/ui/widgets/status_label.py) pour les états ;
- [`SkillTag`](src/ui/widgets/skill_tag.py) pour les skills ;
- [`HairlineSeparator`](src/ui/widgets/hairline.py) pour les séparateurs.

Les fenêtres persistantes exposent `refresh_theme()` et les tests vérifient le
rafraîchissement des dialogues runtime, settings et documentaires.

### États et accessibilité de base

Les tests couvrent maintenant :

- tailles et tooltips des boutons icon-only ;
- focus clavier et ordre de tabulation du compositeur ;
- états désactivé, pressé et hover ;
- statuts succès, danger, warning, loading et muted ;
- textes longs dans les headers, statuts et bulles ;
- rendu Markdown des listes, liens, code et sources.

## Écarts identifiés

### ✅ Amélioré — Styles locaux dans les widgets complexes

**Preuves**

- [`tool_call_widget.py`](src/ui/widgets/tool_call_widget.py) utilise désormais
  des helpers pour les lignes de timeline et les navigateurs de code.
- [`slash_command_popup.py`](src/ui/widgets/slash_command_popup.py) utilise
  désormais un helper pour sa surface, ses états de sélection et sa scrollbar.
- [`document_dialog.py`](src/ui/windows/document_dialog.py) utilise des helpers
  pour la zone de pièces jointes, la réponse et la navigation.
- [`settings_dialog.py`](src/ui/windows/settings_dialog.py) utilise un helper
  pour les accents typographiques récurrents.
- Les styles internes répétés des commandes slash, des surfaces transparentes
  et de l'aperçu des pages documentaires sont maintenant fournis par des
  helpers dédiés dans [`stylesheet.py`](src/ui/stylesheet.py).

**Évaluation**

Les styles locaux restants concernent uniquement le contenu dynamique, les
animations et les compositions propres à une fenêtre. Les structures
réutilisables et leurs états sont centralisés dans
[`stylesheet.py`](src/ui/stylesheet.py).

**Recommandation**

Conserver cette règle lors des prochaines évolutions : extraire un bloc dès
qu'il apparaît sur deux surfaces, sans déplacer artificiellement les styles
HTML ou d'animation qui ne sont pas réutilisables.

### 🟡 MEDIUM — Validation Windows native encore manuelle

Les tests headless ne couvrent pas de manière fiable :

- l'effet Acrylic et les coins natifs Windows 10/11 ;
- le rendu DPI 125/150/200 % ;
- le tray et l'icône de raccourci ;
- les tooltips sur fenêtres frameless translucides ;
- les raccourcis clavier globaux et le comportement multi-écrans.

Ces points doivent rester dans une checklist de release Windows avec captures
clair/sombre et vérification des états interactifs.

### ✅ Résolu — Interpréteurs Python distincts

Le contrôle a été refait le 24/09/2026 avec l'interpréteur `.venv` après
installation de PySide6 6.11.2 et des dépendances importées par les fenêtres et
les skills (`numpy`, `scipy`, `sounddevice`, `requests`, `pandas` et packages
de génération documentaire). Les quatre classes Qt s'exécutent maintenant
normalement.

La commande complète et reproductible de l'audit reste :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests
```

`.venv\Scripts\python.exe` produit désormais le résultat complet de 108/108
tests et reste recommandé pour garantir un environnement reproductible.
Les messages d'erreur audio, TTS et skill invalide apparaissant dans la sortie
sont des scénarios négatifs attendus et validés ; ils ne font pas échouer la
suite.

### ✅ Résolu — Nettoyage des styles de présentation

Les répétitions identifiées dans les accents de paramètres, les surfaces de
réponse, la navigation documentaire et la palette slash ont été regroupées
dans des helpers QSS. Les styles neutres strictement locaux restent autorisés
lorsqu'ils servent uniquement à une composition interne.

## Matrice de conformité

| Règle | État | Preuve |
| --- | --- | --- |
| Couleurs dans les tokens | ✅ | Test d'absence de hex hors tokens. |
| Tokens présents dans les deux thèmes | ✅ | Test de parité des clés. |
| Rafraîchissement dynamique du thème | ✅ | Tests des fenêtres persistantes et `refresh_theme()`. |
| QSS réutilisable | ✅ | Helpers centralisés pour timeline, code outil, slash, réponse, navigation et pièces jointes. |
| États hover/pressed/focus/disabled | ✅ de base | Tests QSS et widgets partagés ; validation native encore manuelle. |
| Boutons icon-only avec tooltip | ✅ | Tests des boutons du compositeur et du header. |
| Focus clavier | ✅ sur le compositeur | Les fenêtres complètes et raccourcis restent à tester manuellement. |
| Assets skills déclarés | ✅ | Test des cinq skills déclarés. |
| Markdown commun | ✅ | Test Qt des listes, liens, code et sources. |
| Contraste et DPI | 🟡 | Contraste sémantique AA automatisé ; icônes, bordures, DPI et rendu restent à valider sous Windows. |

## Plan d'amélioration — état actuel

1. Utiliser systématiquement l'interpréteur `.venv` dans les commandes de
   validation et la documentation. **Mis en place** ; Python système passe
   également les contrôles après installation des dépendances.
2. Ajouter une commande CI de scan des `rgba(...)` hors `design_tokens.py` et
   des dimensions non tokenisées. **Mis en place dans la suite UI** : les
   littéraux `rgba(...)` sont interdits hors tokens et les widgets partagés ne
   peuvent pas introduire de dimensions fixes numériques sans token.
3. Ajouter un fichier d'exceptions contrôlé pour les styles locaux légitimes.
   **Mis en place dans `UI_STYLE_EXCEPTIONS.md`.**
4. Extraire progressivement les QSS réutilisables de la timeline et du
   dialogue documentaire. **Mis en place** pour les lignes de timeline, les
   blocs de code outil, la palette slash, la réponse, la navigation et la barre
   de défilement des pièces jointes.
5. Créer une checklist de release Windows avec thèmes, DPI, Acrylic, tray,
   tooltips et multi-écrans. **Mis en place dans
   `UI_WINDOWS_RELEASE_CHECKLIST.md`.**
6. Ajouter des snapshots ou captures manuelles de référence, sans remplacer
   les tests de comportement. La procédure de captures clair/sombre est
   maintenant incluse dans `UI_WINDOWS_RELEASE_CHECKLIST.md`.

## Conclusion

L'harmonisation visuelle est **conforme et testée** sur les composants
principaux. Les styles réutilisables sont désormais centralisés ;
les seuls styles locaux restants concernent du contenu dynamique ou des
animations. Le seul écart non automatisable reste la validation native
Windows, couverte par la checklist de release. Le code peut continuer à
évoluer si les nouveaux composants utilisent les helpers existants, exposent
`refresh_theme()` et ajoutent leurs états aux tests UI.
