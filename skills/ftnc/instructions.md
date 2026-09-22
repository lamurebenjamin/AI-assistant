# Skill FTNC

Cette skill consulte deux classeurs locaux afin de présenter les FTNC du planner, d'identifier celles à y ajouter et d'afficher le détail d'une référence.

## Déclenchement

Utiliser `ftnc_liste` lorsque l'utilisateur demande notamment :

- « Quel est l'état des lieux des FTNC ? »
- « Où en est-on sur les FTNC ? »
- « Quelles sont les FTNC en cours ou non démarrées ? »
- « Fais-moi une synthèse des FTNC. »
- « Quelles FTNC faut-il ajouter au planner ? »

Utiliser `ftnc_details` lorsque l'utilisateur demande le détail d'une FTNC ou fournit une référence FTNC complète ou partielle.

Ne pas appeler cette skill pour une question sans rapport avec les FTNC. Dans les réponses utilisateur, employer le libellé **FTNC**. La valeur `PPM` est uniquement un critère technique lu dans le classeur de suivi.

## Sources de données

Les chemins et noms de feuilles sont définis en dur dans `generator.py` :

- `FTNC.xlsx`, feuille `Données consolidées` ;
- `Suivi des FTNC €uro.xlsx`, feuille `SUIVI`.

Ne jamais demander à l'utilisateur un chemin de fichier, ne pas accepter de chemin Excel en argument et ne pas modifier les constantes de chemin depuis le LLM.

## Outil de liste et de comparaison

### `ftnc_liste`

Cet outil ne prend aucun argument et retourne une chaîne de texte prête à être affichée.

Il réalise les traitements suivants :

1. Lecture du planner dans `FTNC.xlsx` :
   - colonnes B, C, E et F, renommées respectivement `reference`, `programme`, `statut` et `priorite` ;
   - statuts conservés : `Non démarrées` et `En cours` ;
   - programmes conservés : liste `PROGRAMMES_FTNC` de `generator.py` ;
   - suppression des lignes sans référence ;
   - tri stable par priorité dans l'ordre `Urgent`, `Important`, `Moyen`, `Minimum`, puis par référence ;
   - affichage d'un indicateur visuel correspondant à la priorité.

2. Lecture du suivi €uro :
   - colonne R : statut égal à `En cours` ;
   - colonne K : pôle égal à `PPM` ;
   - colonne H : programme appartenant à `PROGRAMMES_SUIVI` ;
   - préfixe `MWB` pour le type `Structure` et `VLB` pour le type `Carbone` ;
   - aucun préfixe pour les autres types.

3. Comparaison des deux sources :
   - extraction des dix premiers chiffres de chaque référence lorsqu'au moins dix chiffres sont disponibles ;
   - comparaison avec gestion des occurrences en double ;
   - affichage des éléments du suivi absents du planner dans la section `NOUVELLES FTNC À AJOUTER AU PLANNER`.

Après l'appel :

- afficher le texte retourné sans le transformer en structure JSON ou en tableau inventé ;
- conserver l'ordre, les sections, les compteurs, les descriptions et les dates produits par le générateur ;
- ne pas inventer de FTNC, de priorité ou de détail absent du résultat ;
- ne pas annoncer uniquement les FTNC « en cours », car la partie planner inclut aussi les FTNC « non démarrées ».

## Outil de détail

### `ftnc_details`

Argument obligatoire :

- `reference` : référence complète ou partielle, par exemple `MWB1234567890`, `VLB1234567890` ou `1234567890`.

La recherche :

- ignore la casse et les caractères non alphanumériques ;
- interroge à la fois le planner et le suivi €uro ;
- compare la saisie à la référence, au numéro et à l'identifiant numérique selon la source ;
- accepte une correspondance exacte ou une saisie contenue dans la valeur normalisée ;
- peut retourner plusieurs correspondances.

Après l'appel :

- afficher le texte retourné par le générateur ;
- conserver l'indication de la source pour chaque correspondance ;
- pour une ligne du planner, afficher la priorité ;
- pour une ligne du suivi €uro, conserver le type, le pôle, la pièce, la référence pièce, la quantité, la date de début et la description ;
- si aucune FTNC n'est trouvée, reprendre le message d'absence retourné ;
- ne pas exposer `ligne_excel`, car cette donnée interne n'est pas incluse dans le rendu du générateur.

## Gestion des erreurs

- Si `reference` est vide, laisser remonter l'erreur indiquant que la référence FTNC est obligatoire.
- Si un fichier est introuvable, afficher clairement l'erreur retournée par le générateur sans fabriquer de résultat.
- Si la feuille `SUIVI` est introuvable, afficher clairement l'erreur retournée.
- Ne jamais prétendre avoir lu un classeur sans avoir appelé l'outil approprié.

## Règles de réponse

- Dire **FTNC** dans les descriptions et les réponses métier.
- Conserver `PPM` uniquement lorsqu'il est utile d'expliquer le filtre technique ou dans le détail brut retourné par le générateur.
- Utiliser le contenu exact retourné par le générateur comme source de vérité.
- Ne pas annoncer de lien `ftnc://`, d'action `show_ftnc_detail`, d'objet `action.arguments` ni de sortie Markdown structurée : `generator.py` retourne uniquement du texte.
