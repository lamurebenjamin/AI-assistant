## Skill Excel

Cette skill permet de créer des classeurs Microsoft Excel au format `.xlsx`.

### Outil

`create_excel`

Arguments obligatoires :
- `filename` : nom du fichier Excel, avec ou sans l'extension `.xlsx`
- `sheet_name` : nom de la feuille Excel
- `headers` : liste ordonnée des en-têtes de colonnes
- `rows` : liste ordonnée des lignes de données

Le classeur Excel est créé automatiquement dans le dossier `output/` du projet.

### Règles

- Utiliser l'outil lorsqu'un fichier Excel est réellement demandé.
- Ne jamais utiliser cette skill pour créer un document Word ou un fichier `.docx`.
- Ne jamais prétendre qu'un classeur Excel a été créé sans appeler l'outil.
- Ne pas fournir de chemin arbitraire : le générateur contrôle le dossier de sortie.
- Chaque ligne doit contenir le même nombre de valeurs que la liste des en-têtes.
- Après l'exécution, utiliser le résultat du tool pour confirmer le chemin du fichier `.xlsx`.

### Exemple d'appel

```json
{
  "filename": "resultats_calculs.xlsx",
  "sheet_name": "Résultats",
  "headers": ["Cas", "Charge", "Contrainte"],
  "rows": [
    ["CAS_001", 12500, 245.6],
    ["CAS_002", 13800, 267.2]
  ]
}
```

### Dépendance Python

```bash
pip install openpyxl
```
