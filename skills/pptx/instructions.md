## Skill PPTX

Cette skill permet de creer des presentations Microsoft PowerPoint au format `.pptx`.

### Outil

`create_pptx`

Arguments obligatoires :
- `filename` : nom du fichier PowerPoint, avec ou sans l'extension `.pptx`
- `title` : titre principal de la presentation
- `subtitle` : sous-titre de la diapositive de couverture
- `slides` : liste ordonnee des diapositives de contenu

Chaque element de `slides` doit contenir :
- `title` : titre de la diapositive
- `bullets` : liste ordonnee des points a afficher

La presentation est creee automatiquement dans le dossier `output/` du projet.

### Regles

- Utiliser l'outil lorsqu'un fichier PowerPoint est reellement demande.
- Ne jamais utiliser cette skill pour creer un fichier Word, Excel ou PDF.
- Ne jamais pretendre qu'une presentation a ete creee sans appeler l'outil.
- Ne pas fournir de chemin arbitraire : le generateur controle le dossier de sortie.
- Privilegier des diapositives synthetiques avec des points courts et lisibles.
- Apres l'execution, utiliser le resultat du tool pour confirmer le chemin du fichier `.pptx`.

### Exemple d'appel

```json
{
  "filename": "revue_calculs.pptx",
  "title": "Revue des calculs",
  "subtitle": "Synthese des resultats",
  "slides": [
    {
      "title": "Objectifs",
      "bullets": [
        "Presenter les hypotheses",
        "Synthétiser les resultats",
        "Identifier les actions restantes"
      ]
    },
    {
      "title": "Conclusion",
      "bullets": [
        "Les criteres principaux sont respectes",
        "Une verification complementaire reste a realiser"
      ]
    }
  ]
}
```

### Dependance Python

```bash
pip install python-pptx
```

Le nom du paquet a installer est `python-pptx`, mais l'import Python utilise `pptx`.
