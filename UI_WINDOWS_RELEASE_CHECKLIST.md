# Checklist de validation UI Windows

Cette checklist complète les tests headless. Elle doit être exécutée avant
une release ou une modification touchant le thème, les fenêtres frameless,
les icônes ou les raccourcis système.

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
- [ ] Vérifier le contraste du texte secondaire, des icônes et des bordures dans
  les deux thèmes.

## Windows natif

- [ ] Tester le rendu Acrylic et les coins arrondis sur Windows 10 et Windows
  11 lorsque les deux plateformes sont disponibles.
- [ ] Tester les facteurs DPI 100 %, 125 %, 150 % et 200 %.
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
