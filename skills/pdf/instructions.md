## Skill PDF

Cette skill permet de creer des documents PDF au format `.pdf`.

### Outil

`create_pdf`

Arguments obligatoires :
- `filename` : nom du fichier PDF, avec ou sans l'extension `.pdf`
- `title` : titre principal du document
- `paragraphs` : liste ordonnee des paragraphes

Le fichier PDF est cree automatiquement dans le dossier `output/` du projet.

### Regles

- Utiliser l'outil lorsqu'un fichier PDF est reellement demande.
- Ne jamais utiliser cette skill pour creer un fichier Word `.docx` ou Excel `.xlsx`.
- Ne jamais pretendre qu'un PDF a ete cree sans appeler l'outil.
- Ne pas fournir de chemin arbitraire : le generateur controle le dossier de sortie.
- Apres l'execution, utiliser le resultat du tool pour confirmer le chemin du fichier `.pdf`.

### Exemple d'appel

```json
{
  "filename": "rapport_calcul.pdf",
  "title": "Rapport de calcul",
  "paragraphs": [
    "Objet : synthese des resultats de calcul.",
    "Le cas CAS_001 respecte les criteres definis.",
    "Conclusion : le dimensionnement est valide."
  ]
}
```

### Dependance Python

```bash
pip install reportlab
```
