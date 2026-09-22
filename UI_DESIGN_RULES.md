# Règles d'architecture UI et de cohérence visuelle

Ce document est la référence obligatoire pour toute nouvelle fenêtre, tout
nouveau widget et toute nouvelle fonctionnalité visuelle.

## 1. Sources de vérité

Une valeur visuelle ne doit avoir qu'une seule source :

| Besoin | Source obligatoire |
|---|---|
| Couleurs liées au thème clair/sombre | `src/ui/design_tokens.py` |
| Typographies, tailles de texte, espacements, rayons et dimensions communes | `src/ui/design_tokens.py` |
| Icônes SVG et épaisseurs de traits | `src/ui/icons.py` |
| Styles QSS réutilisables | `src/ui/stylesheet.py` |
| Palette Qt, thème global, acrylique et tooltips | `src/ui/theme.py` |
| Comportement réutilisable d'un contrôle | `src/ui/widgets/` (`window_chrome`, `hairline`, `skill_tag`, `status_label`, `composer_bar`, …) |
| Formatage des statuts Raisonnement/Exécution | `src/ui/status_formatters.py` |
| Conversion Markdown/HTML | `src/rendering/markdown.py` |
| Valeurs métier et préférences utilisateur | `src/config/schema.py` et `src/config/manager.py` |

Les fenêtres (`src/ui/windows/`) orchestrent les composants. Elles ne doivent
pas devenir une deuxième bibliothèque de styles.

## 2. Règles obligatoires pour tout nouveau feature

1. Rechercher d'abord un token, une icône, une fonction QSS ou un widget
   existant avant d'ajouter du code.
2. Ne jamais écrire directement une couleur (`#...`, `rgba(...)`) dans un
   widget si elle appartient au thème. Ajouter le token dans les deux thèmes.
3. Ne jamais dupliquer une dimension commune (`QSize`, `setFixedHeight`,
   marges, rayons, tailles d'icône). Ajouter ou réutiliser une constante dans
   `design_tokens.py`.
4. Ne jamais créer une icône SVG dans une fenêtre si elle est réutilisable.
   Ajouter son chemin dans `icons.py`.
5. Ne jamais copier un bloc `setStyleSheet()` utilisé par plusieurs écrans.
   Extraire une fonction dans `stylesheet.py`.
6. Toute valeur dépendant du thème doit être relue dynamiquement après le
   changement de thème. Ne pas capturer une couleur de thème dans une
   constante locale au niveau du module.
7. Un widget réutilisable doit exposer une API claire (`set_state`,
   `set_enabled`, `set_variant`, signaux Qt) plutôt que demander à chaque
   fenêtre de modifier ses enfants internes.
8. Les états visuels doivent être explicitement définis : normal, hover,
   pressed, focus, disabled, actif, erreur et chargement si applicables.
9. Le texte utilisateur doit respecter les traductions et les formats
   existants. Ne pas introduire de libellé codé en dur dans plusieurs fichiers.
10. Une fonctionnalité doit conserver les tailles, marges, polices, contrastes
    et comportements des composants existants, sauf décision documentée.

## 3. Organisation recommandée

### `design_tokens.py`

Contient uniquement les tokens :

- couleurs sémantiques (`COLOR_TEXT_PRIMARY`, `COLOR_DANGER`, etc.) ;
- tailles de texte (`SIZE_SM`, `SIZE_MD`, etc.) ;
- typographies ;
- espacements et rayons ;
- dimensions communes (`HEADER_HEIGHT`, `ICON_SIZE_CLOSE`, etc.).

Un token doit décrire son rôle, pas son emplacement. Préférer
`ICON_SIZE_CLOSE` à `WINDOW_X_CLOSE_SIZE`.

### `icons.py`

Contient :

- les chemins SVG partagés ;
- la couleur et l'épaisseur par défaut ;
- l'initialisation des variantes clair/sombre ;
- les helpers de chargement d'icônes locales.

Les widgets qui dessinent eux-mêmes une icône doivent justifier ce choix
(animation continue, géométrie dynamique ou niveau audio). Dans ce cas, la
géométrie et l'épaisseur doivent tout de même venir des tokens.

### `stylesheet.py`

Chaque fonction doit retourner un bloc QSS cohérent et réutilisable. Les
sélecteurs doivent être limités à un composant ou à un rôle (`#SaveBtn`,
`#Header`, `QToolButton`). Les styles locaux sont réservés à un état réellement
spécifique à un widget.

### `widgets/`

Un widget partagé doit :

- posséder une responsabilité unique ;
- recevoir ses dimensions et variantes via tokens ;
- ne pas connaître la fenêtre qui l'héberge ;
- émettre des signaux au lieu de modifier directement un autre écran ;
- gérer ses états dans un seul endroit ;
- rester testable sans lancer toute l'application.

### `status_formatters.py`

Ce module formate les durées et les titres d'état des blocs d'activité. Les
fenêtres et widgets ne doivent pas reconstruire localement les textes
`Réflexion de Xs` ou `X étape(s) complétée(s) en Xs`.

### `windows/`

Une fenêtre doit :

- composer des widgets existants ;
- appliquer le thème global ;
- connecter les signaux aux actions métier ;
- ne contenir que les styles propres à cette fenêtre ;
- éviter les valeurs visuelles en dur.

## 4. Conventions de nommage

- `COLOR_*` : couleurs sémantiques.
- `FONT_*` : familles de polices.
- `SIZE_*` : tailles de texte.
- `SPACING_*` : espacements.
- `RADIUS_*` : rayons.
- `ICON_SIZE_*` : dimensions d'icônes.
- `BUTTON_SIZE_*` : dimensions de boutons.
- `*_HEIGHT`, `*_WIDTH` : dimensions de conteneurs.
- `qss_*()` : blocs QSS réutilisables.
- `create_*_icon()` : création d'icônes.

Éviter les noms basés sur une valeur (`GRAY_14`, `MARGIN_7`) sauf token
mathématique ou contrainte technique explicitement documentée.

## 5. Thèmes et contraste

Chaque nouveau token de couleur doit exister dans `THEME_DARK` et
`THEME_LIGHT`. Les couleurs doivent être sémantiques et testées dans les deux
thèmes.

Règles minimales :

- texte principal lisible sur son arrière-plan ;
- texte secondaire réservé aux informations secondaires ;
- texte désactivé jamais utilisé pour une action active ;
- état actif/hover visible sans dépendre uniquement de la couleur ;
- icônes et texte d'un même contrôle utilisent le même état ;
- aucune couleur sombre codée en dur dans un widget clair/sombre.

## 6. Layout et dimensions

- Utiliser les layouts Qt plutôt que des coordonnées fixes.
- Utiliser `setSizePolicy` avant `setFixedWidth`/`setFixedHeight`.
- Réserver les dimensions fixes aux contrôles dont la taille est une
  contrainte UX réelle.
- Utiliser `HEADER_HEIGHT`, `BUTTON_SIZE_HEADER`, `ICON_SIZE_*`,
  `COMPOSER_HEIGHT` et les tokens associés pour les composants communs.
- Ne pas modifier la taille d'une icône sans vérifier le bouton, son alignement
  et son état hover.
- Vérifier les petites largeurs de fenêtre et les textes longs.

## 7. Icônes et boutons

- Réutiliser les icônes du registre avant d'en ajouter une nouvelle.
- Garder un bouton à une seule responsabilité.
- Utiliser un tooltip pour une action icon-only.
- Conserver une zone cliquable suffisamment grande, même si l'icône est
  visuellement petite.
- Ne pas confondre la taille du bouton et la taille de son icône.
- Centraliser les tailles de fermeture, copie, lecture, micro et envoi.

## 8. Rendu Markdown et contenu riche

- Tous les appels doivent passer par `src/rendering/markdown.py`.
- Ne pas générer une variante locale de Markdown dans un widget.
- Les listes, paragraphes, titres et blocs de code doivent garder les mêmes
  règles dans toutes les fenêtres.
- Toute propriété HTML doit être vérifiée avec le moteur rich-text Qt, pas
  seulement avec un navigateur.
- Les changements de structure Markdown doivent être testés avec listes à
  puces, listes numérotées, texte long, code et liens.

## 9. Checklist avant validation

### Architecture

- [ ] Une recherche a été faite avant d'ajouter un composant.
- [ ] Aucun token, style QSS ou icône n'est dupliqué.
- [ ] Les valeurs nouvelles sont dans le bon module de référence.
- [ ] Le widget ne dépend pas d'une fenêtre spécifique.

### Visuel

- [ ] Thème sombre vérifié.
- [ ] Thème clair vérifié.
- [ ] Normal, hover, pressed, focus et disabled vérifiés.
- [ ] Textes longs et fenêtre étroite vérifiés.
- [ ] Icône, texte et zone cliquable alignés.
- [ ] Contraste et lisibilité vérifiés.

### Technique

- [ ] Compilation Python réussie.
- [ ] `git diff --check` réussi.
- [ ] Test ciblé du widget ou du rendu ajouté/exécuté.
- [ ] Aucun nouveau `setStyleSheet()` dupliqué.
- [ ] Aucun nouveau littéral de couleur ou de dimension sans justification.

## 10. Audit actuel et plan de migration

### Déjà centralisé

- Couleurs principales et variantes de thème.
- Typographies, tailles de texte et rayons.
- Hauteur d'en-tête, tailles de boutons et icônes principales.
- Registre SVG partagé.
- Blocs QSS génériques.
- Rendu Markdown commun.

### À centraliser en priorité

1. Les couleurs et alpha encore présents dans `theme.py`,
   `assistant_window.py`, `settings_dialog.py`, `tool_call_widget.py`,
   `chat_bubble.py` et `animated_buttons.py`.
2. Les dimensions audio de `audio_bars.py` (`106x24`, hauteurs, largeurs et
   espacements de barres).
3. Les dimensions de `chat_bubble.py` et du tag de compétence.
4. Les marges et tailles répétées dans `document_dialog.py`.
5. Les tailles de scrollbar, champs, boutons standards et menus dans
   `stylesheet.py`.
6. Les couleurs d'état de `icons.py` et les couleurs d'erreur des bulles.
7. Les libellés communs et messages d'état, à regrouper dans un module de
   chaînes si la localisation devient nécessaire.

### Méthode de migration

Pour chaque groupe :

1. recenser les valeurs et leur rôle ;
2. choisir un nom sémantique ;
3. ajouter la valeur dans les thèmes si nécessaire ;
4. remplacer les usages sans changer le rendu ;
5. tester les deux thèmes et les états interactifs ;
6. supprimer les anciennes valeurs locales ;
7. vérifier les doublons avec une recherche ciblée.

Ne pas faire une migration globale non testée : chaque groupe doit rester
visuellement équivalent avant et après.

## 11. Règle de revue

Une pull request ou une modification UI qui introduit une valeur visuelle
locale sans justification doit être refusée. La question de revue standard
est :

> « Cette valeur existait-elle déjà, et si non, pourquoi n'est-elle pas un
> token, un style QSS ou un composant partagé ? »

## 12. Assets et identité visuelle

Les assets externes font partie de l'interface et suivent les mêmes règles que
les widgets :

- l'icône applicative source doit exister en SVG ou PNG avec transparence
  contrôlée ; les déclinaisons `.ico` et `.webp` sont des exports ;
- une icône de skill est déposée dans le dossier du skill, porte le nom
  `icon.svg` ou `icon.png` et reste lisible sur les surfaces claire et sombre ;
- les icônes doivent conserver une zone de sécurité et ne pas incorporer de
  couleur de thème irréversible si elles sont recolorées par l'application ;
- tout fallback est explicite : icône générique de skill si l'asset est
  absent, logo application si l'icône de fenêtre est indisponible ;
- toute nouvelle taille d'asset doit être ajoutée aux tokens et vérifiée dans
  le header, les menus et les listes avant validation.

## 13. Accessibilité et états

Chaque action interactive doit avoir une zone cliquable d'au moins
`BUTTON_SIZE_HEADER`, un tooltip pour les boutons sans texte et un état
focus visible. Un état ne doit jamais être signalé par la couleur seule :
ajouter un libellé, une icône, une variation de forme ou un changement de
contenu. Les textes longs doivent rester lisibles sans chevauchement et les
contrastes sont vérifiés dans les deux thèmes.

Les états à vérifier pour chaque composant applicable sont : normal, hover,
pressed, focus, disabled, chargement, succès et erreur. Un changement de thème
doit reconstruire les valeurs dépendantes du thème ; aucune couleur ne doit
être capturée une seule fois au niveau du module.

## 14. Validation avant modification ou ajout

Avant une PR UI :

1. rechercher un token, QSS, icône ou widget existant ;
2. ajouter les nouvelles valeurs dans les deux thèmes et choisir un nom de
   rôle, jamais un nom de couleur brute ;
3. vérifier les deux thèmes, les états interactifs, les textes longs et une
   fenêtre étroite ;
4. lancer la compilation Python, les tests UI ciblés et `git diff --check` ;
5. décrire toute exception visuelle dans la PR, avec sa raison et son périmètre.
6. exécuter la checklist Windows de
   [`UI_WINDOWS_RELEASE_CHECKLIST.md`](UI_WINDOWS_RELEASE_CHECKLIST.md) pour
   toute modification du thème, des fenêtres frameless, des icônes ou des
   raccourcis système.

Une modification qui ajoute un `setStyleSheet()` local, une valeur visuelle
en dur ou une taille non tokenisée doit être refusée tant que l'exception
n'est pas documentée.
