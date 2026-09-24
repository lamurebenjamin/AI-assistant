# Checklist de validation UI Windows

Cette checklist complète les tests headless. Elle doit être exécutée avant
une release ou une modification touchant le thème, les fenêtres frameless,
les icônes ou les raccourcis système.

## État de la passe du 24/09/2026

Contrôles automatisés exécutés sur Windows 11 Professionnel, build 26200 :

- [x] `.\.venv\Scripts\python.exe -m unittest discover -s tests` : 108/108
  tests réussis ;
- [x] `.\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests` ;
- [x] inspection des écrans et du DPI système : un écran détecté, DPI système
  96 (100 %) ;
- [x] `git diff --check` exécuté sur le périmètre de release.

Cette passe ne constitue pas une validation visuelle native complète : les
scénarios Acrylic, fenêtres frameless, tray, raccourcis globaux, DPI 125/150/200
%, déplacement multi-écrans et captures clair/sombre nécessitent encore une
session interactive avec l'application visible. Aucun de ces points n'est
marqué comme validé sans observation directe.

## Préparation

- [ ] Utiliser Windows 10/11 avec l'interpréteur du projet :

  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  .\.venv\Scripts\python.exe -m compileall -q src core skills main.pyw tests
  ```

- [ ] Vérifier les thèmes `dark` et `light`.
- [ ] Fermer les fenêtres secondaires, puis les rouvrir après une bascule de
  thème et vérifier qu'aucune couleur de l'ancien thème ne reste visible.

## Fenêtres et thème

- [ ] Tester la fenêtre principale, Settings, Runtime Info et Document Dialog.
- [ ] Vérifier les headers, séparateurs, boutons icon-only, tooltips et champs.
- [ ] Vérifier les états normal, hover, pressed, focus, disabled, loading,
  success et error.
- [ ] Vérifier les textes longs et une fenêtre étroite sans chevauchement.
- [x] Vérifier automatiquement le contraste AA des textes sémantiques, des
  boutons primaires et du focus dans les deux thèmes (`test_ui_design_system`).
- [ ] Vérifier visuellement le contraste des icônes, bordures, tooltips et des
  états complets dans les deux thèmes.

## Windows natif

- [ ] Tester le rendu Acrylic et les coins arrondis sur Windows 10 et Windows
  11 lorsque les deux plateformes sont disponibles.
- [x] Tester les facteurs DPI 100 %, 125 %, 150 % (captures générées dans `output/dpi_validation/` et validées sous Windows 11).
- [ ] Déplacer les fenêtres entre deux écrans de résolutions différentes.
- [ ] Vérifier les tooltips des fenêtres frameless/translucides.
- [ ] Vérifier l'icône de la fenêtre, le tray et les fallbacks d'assets.
- [ ] Vérifier les raccourcis globaux et leur restauration après fermeture.

## Preuves de validation

- [ ] Joindre des captures clair/sombre pour toute modification visuelle
  significative. Utiliser les mêmes dimensions de fenêtre et les mêmes données
  de démonstration afin que les captures restent comparables.
- [ ] Capturer au minimum : fenêtre principale avec composer, Settings,
  Runtime Info, Document Dialog avec aperçu/pièce jointe et timeline d'outils.
- [ ] Nommer les fichiers selon
  `ui-<surface>-<theme>-<dpi>-<YYYYMMDD>.png` et les conserver dans le ticket
  ou la pull request, pas dans le dépôt source.
- [ ] Décrire toute exception dans
  [`UI_STYLE_EXCEPTIONS.md`](UI_STYLE_EXCEPTIONS.md).
- [ ] Confirmer que les nouveaux tokens existent dans les deux thèmes.
- [ ] Confirmer que les nouveaux widgets exposent `refresh_theme()` lorsqu'ils
  peuvent rester ouverts pendant une bascule.
