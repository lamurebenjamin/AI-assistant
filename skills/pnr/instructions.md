# Skill PNR : consultation des nomenclatures

## Objectif

Lorsqu'un utilisateur fournit une reference article, utiliser `nomenclature`
pour consulter `PNR.db` et afficher chaque nomenclature contenant cette reference,
depuis sa racine (niveau 0) jusqu'au niveau 3 inclus.

## Declenchement

Utiliser ce skill pour les demandes d'information sur une reference, sa nomenclature,
sa racine ou ses niveaux 0, 1, 2 et 3. L'outil accepte une reference exacte.
Ne pas annoncer de resultat avant d'avoir execute l'outil.

## Entree et sortie

Entree : `reference` (chaine non vide, espaces exterieurs ignores).
Sortie : texte, une section par racine distincte, avec toutes les branches de la
nomenclature jusqu'au niveau 3. Chaque occurrence est presentee sous la forme :

    Niveau N : designation (ref Rev.issue)

La reference recherchee est signalee sur les lignes visibles par
`<- reference recherchee`. Si elle est au-dela du niveau 3, une mention
explicite indique que l'occurrence est masquee par la limite d'affichage.
Une revision absente est rendue par `Rev.?`.

## Configuration

Lire le chemin dans le `config.json` existant, sous
`skills.pnr.database_path`. Le chemin peut etre absolu ou relatif a la
racine du projet. Ne pas coder en dur de chemin utilisateur et ne pas remplacer
les autres entrees de `config.json`.

## Regles metier et hypothese a valider

- `bom.parent_id` est suppose pointer vers `bom.id`.
- Une racine est une ligne `bom` dont `parent_id IS NULL`.
- Chaque occurrence de la reference est remontee a sa racine.
- Plusieurs occurrences sous une meme racine produisent une seule section.
- Plusieurs racines produisent plusieurs sections.
- La sortie contient toutes les branches de chaque racine jusqu'au niveau 3,
  et non uniquement le chemin vers la reference.
- `bom.root_id` et `bom.parent_article_ref` ne sont pas utilises dans cette
  premiere version : leur semantique reste a verifier sur la base reelle.

## Cas particuliers

- Reference absente de `articles` et de `bom` : message d'absence.
- Reference presente dans `articles` mais absente de `bom` : fiche article,
  puis mention de l'absence de nomenclature.
- Article d'une occurrence absent de `articles` : `Designation inconnue`.
- Parent manquant, cycle, schema invalide, configuration absente ou base
  inaccessible : erreur explicite ; ne pas inventer de nomenclature.

## Contraintes techniques

`generator.py` contient la logique metier ; `skill.py` expose FastMCP et le
wrapper UI. Ouvrir SQLite en lecture seule (`mode=ro`) et parametrer les
references SQL. Ne pas modifier la base. Aucun fichier de sortie n'est cree.

## Verification

Verifier l'import, la decouverte du skill, le schema LLM, l'exposition MCP
et une recherche sur la vraie base. Si la remontée echoue, examiner d'abord
la relation reelle entre `parent_id`, `id`, `root_id` et `parent_article_ref`.
