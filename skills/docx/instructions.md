# Skill DOCX

Cette skill permet de créer des documents Microsoft Word (.docx).

## Outil

`create_docx`

Arguments obligatoires :

- `filename` : nom du fichier
- `title` : titre principal
- `paragraphs` : liste ordonnée de paragraphes

Le fichier est créé automatiquement dans le dossier `output/` du projet.

## Règles

- Utiliser l'outil lorsqu'un fichier Word est réellement demandé.
- Ne jamais prétendre qu'un fichier a été créé sans appeler l'outil.
- Ne pas fournir de chemin arbitraire : le générateur contrôle le dossier de sortie.
- Après l'exécution, utiliser le résultat du tool pour confirmer le chemin du fichier.
