# Règles Impératives de Développement pour les LLM & Assistants IA

> [!IMPORTANT]
> **RÈGLE FONDAMENTALE DE GOUVERNANCE**
> À chaque action, modification ou création effectuée par un modèle d'IA (LLM / Agent de programmation) sur ce projet, **la documentation**, **les tests**, et **le code source unique (Single Source of Truth)** doivent être **OBLIGATOIREMENT** mis à jour et vérifiés avant de clore l'intervention.

---

## 1. Mise à jour obligatoire des Tests (Non-Régression & Couverture)
1. **Zéro régression** : Toute modification apportée au code doit laisser la suite de tests complète au vert (`python -m unittest discover tests`).
2. **Nouveaux tests obligatoires** :
   - Pour chaque **bug corrigé**, un test unitaire reproduisant le cas limite et validant sa résolution doit être ajouté.
   - Pour chaque **nouvelle fonctionnalité**, composant ou skill ajouté, des tests unitaires correspondants doivent être créés dans `tests/`.
3. **Validation de l'isolation** : Toute nouvelle vue ou fenêtre modale doit posséder un test garantissant l'absence de superposition visuelle ou d'état fantôme.

---

## 2. Respect absolu de la Source Unique de Vérité (Single Source of Truth)
Aucune duplication de définition n'est tolérée dans le projet :
1. **Icônes (`src/ui/icons.py`)** :
   - TOUTES les icônes de l'application DOIVENT provenir exclusivement du registre central `_SVG` dans `src/ui/icons.py`.
   - Tout nouveau bouton (en-tête, compositeur, action) doit consommer `ICONS` ou `ICONS_DARK`. Aucun tracé manuel `QPainter` ad-hoc n'est autorisé.
   - Les tests de `tests/test_icon_consistency.py` doivent passer systématiquement.
2. **Tokens de Design (`src/ui/design_tokens.py`)** :
   - Interdiction formelle d'écrire des couleurs hexadécimales brutes (`#...`) ou des valeurs numériques de dimension en dur dans les composants UI.
   - Utiliser systématiquement les tokens `THEME_DARK`, `THEME_LIGHT`, `BUTTON_SIZE_*`, `ICON_SIZE_*`, `INPUT_HEIGHT`, etc.
3. **Tooltips (`src/ui/fluent_compat.py`)** :
   - Tous les tooltips doivent être installés via la fonction utilitaire unique `install_tooltip(widget, text)` garantissant l'effet Fluent Windows 11 natif (`ToolTipFilter`).
4. **Composants d'onglets (`QStackedWidget`)** :
   - Utiliser exclusivement `QStackedWidget` natif avec synchronisation propre `Pivot.currentItemChanged` pour éviter tout bug de superposition graphique.

---

## 3. Mise à jour obligatoire de la Documentation
À chaque intervention :
1. **Documentation du code** :
   - Mettre à jour les docstrings et les annotations de type (`typing`).
   - Tout argument, retour et exception possible doit être documenté.
2. **Documentation globale du projet** :
   - Si une commande, une dépendance, un skill ou une configuration est ajouté ou modifié, mettre à jour immédiatement :
     - `README.md`
     - `skills/README.md`
     - Les fichiers d'audit et de conformité (`MAINTAINABILITY_AUDIT.md`, `UI_DESIGN_RULES.md`).
3. **Traçabilité** :
   - Documenter explicitement la cause racine du problème et la solution apportée dans la réponse à l'utilisateur.

---

## 4. Sécurité & Robustesse
1. **Pas de chemins absolus en dur** : Ne jamais intégrer de chemins absolus spécifiques à un utilisateur ou à une machine dans le code ou les compétences. Utiliser `APP_DIR`, `Path.home()` ou des chemins relatifs configurables.
2. **Validation des entrées utilisateur & LLM** : Tout argument passé à un outil ou au gestionnaire de processus (`llama-server`, `nvidia-smi`) doit être nettoyé et validé (`Path(filename).name`, `shlex`, vérification d'existence).
3. **Gestion des ressources** :
   - Fermer systématiquement les handles de fichiers, flux audio et threads d'arrière-plan (`shutdown_background_threads`).
   - Nettoyer les fichiers temporaires créés sur le disque.

---

## 5. Checklist de Clôture d'une Intervention LLM
Avant de considérer une tâche comme achevée, le LLM doit valider cette checklist :
- [ ] Le code résout exactement le besoin formulé.
- [ ] Les tests existants et nouveaux passent avec succès (`python -m unittest discover tests`).
- [ ] La règle de source unique (icônes, tokens, tooltips) est respectée.
- [ ] Les linters et vérificateurs de syntaxe ne signalent aucune erreur critique (`ruff check`).
- [ ] La documentation (code, README, règles) a été actualisée pour refléter les changements.
- [ ] Aucun chemin en dur ou secret n'a été introduit.
