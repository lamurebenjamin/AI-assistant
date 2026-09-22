# Exceptions de styles UI

Ce fichier documente les styles locaux autorisés lorsqu'une extraction vers
[`src/ui/stylesheet.py`](src/ui/stylesheet.py) réduirait la lisibilité ou ne
pourrait pas représenter un contenu dynamique.

## Exceptions autorisées

| Surface | Justification | Condition |
| --- | --- | --- |
| [`document_dialog.py`](src/ui/windows/document_dialog.py) | Aperçu documentaire, éditeur inline et HTML dynamique ont une composition spécifique. | Les surfaces de réponse, navigation, pièces jointes, lignes transparentes et contrôles de pages passent par `stylesheet.py`; seules les règles spécifiques au contenu restent locales. |
| [`tool_call_widget.py`](src/ui/widgets/tool_call_widget.py) | Timeline d'outils et blocs de code composés dynamiquement. | Les lignes, blocs de code, surfaces transparentes et états partagés passent par `stylesheet.py`; les styles d'animation et de contenu restent locaux. |
| [`slash_command_popup.py`](src/ui/widgets/slash_command_popup.py) | Popup transitoire avec sélection et contenu variable. | La surface, les états de liste et les styles des labels passent par `stylesheet.py`; seuls les contenus dynamiques restent locaux. |
| [`settings_dialog.py`](src/ui/windows/settings_dialog.py) | Sections de paramètres hétérogènes et contrôles conditionnels. | Les accents typographiques passent par `qss_settings_emphasis()`; réutiliser les composants partagés dès qu'une structure se répète. |
| [`runtime_info_dialog.py`](src/ui/windows/runtime_info_dialog.py) | Carte runtime spécifique à la présentation de métriques. | Le style doit être reconstruit par `refresh_theme()`. |
| [`src/rendering/markdown.py`](src/rendering/markdown.py) | HTML rich-text généré pour Qt. | Les couleurs injectées doivent provenir du thème actif. |

## Règles de revue

Une nouvelle exception doit :

1. être ajoutée ici avec une justification précise ;
2. utiliser les tokens pour toute valeur dépendante du thème ;
3. exposer `refresh_theme()` si le widget reste ouvert pendant une bascule de
   thème ;
4. ajouter ou mettre à jour un test dans
   [`tests/test_ui_design_system.py`](tests/test_ui_design_system.py) lorsque
   l'exception introduit un nouvel état ou une nouvelle dimension ;
5. être supprimée dès qu'un composant partagé couvre correctement le besoin.

Une exception ne doit pas servir à contourner la centralisation d'une couleur,
d'une dimension ou d'un état interactif réutilisable.