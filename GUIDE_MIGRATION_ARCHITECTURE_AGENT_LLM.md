# Guide d'implémentation de la nouvelle architecture

> Instructions opérationnelles destinées à un agent LLM intervenant sur le projet **Assistant IA Local**. Ce document décrit une architecture cible **proposée**, et non un constat vérifié dans les sources. Il s'appuie sur le README fourni ; l'agent doit examiner le dépôt réel avant de modifier quoi que ce soit.

## 1. Mission et résultat attendu

Améliorer progressivement l'architecture de l'application Windows/PySide6 sans changer son comportement utilisateur. Séparer l'orchestration métier de l'interface, expliciter les dépendances, clarifier le cycle de vie des opérations asynchrones et ajouter des tests de comportement. Ne pas effectuer une réécriture générale ni déplacer tous les modules en une seule livraison.

À la fin de chaque lot, livrer le code modifié, les tests associés, la documentation mise à jour, les commandes de validation et leurs résultats réels. Si l'environnement ne permet pas de tester Windows, CUDA, le microphone ou le serveur local, le signaler explicitement : ne jamais présenter une validation statique comme une validation complète.

## 2. Références du dépôt à lire avant toute modification

Lire dans cet ordre, **si ces fichiers existent dans le dépôt effectivement fourni** :

1. `AGENTS.md` et `.agents/rules/llm_development_rules.md` ; appliquer leurs règles avant ce guide en cas de conflit.
2. `README.md`, `docs/audits/AUDIT_GLOBAL.md`, `docs/audits/MAINTAINABILITY_AUDIT.md`.
3. `docs/development/NAMING_CONVENTION.md`, `docs/ui/UI_DESIGN_RULES.md` et `docs/release/UI_WINDOWS_RELEASE_CHECKLIST.md`.
4. Les points d'entrée, imports et tests réellement présents : `main.pyw`, `src/app/application.py`, `src/ui/windows/`, `src/llm/`, `src/documents/`, `src/tts/`, `core/`, `tests/` et les fichiers de dépendances.

Le README décrit des patchs de refactorisation et non nécessairement un dépôt entièrement intégré. Vérifier quels fichiers sont effectivement présents. Ne jamais inventer une classe, une API, une signature ou un test à partir de la seule arborescence documentaire.

## 3. Règles non négociables

- Préserver les fonctionnalités, raccourcis, fenêtres, comportements de streaming, commandes slash, pièces jointes, skills MCP, configuration, thèmes, lancement via `main.pyw` et arrêt propre.
- Conserver les façades et les signatures publiques utilisées par les tests, scripts, raccourcis et autres modules, sauf migration explicitement couverte par tests.
- Ne pas modifier la logique métier en même temps qu'un déplacement de fichier. Séparer déplacement, adaptation des imports et évolution fonctionnelle en lots contrôlables.
- Ne pas introduire de dépendance de `domain` ou `application` vers `PySide6`, `QWidget`, les styles QSS ou les fenêtres. Les adaptateurs Qt appartiennent à `ui` ou `infrastructure`.
- Ne pas introduire de singleton global supplémentaire pour résoudre les dépendances. Réutiliser temporairement les composants existants lorsque nécessaire, puis injecter les dépendances au point de composition.
- Ne jamais mettre à jour un widget depuis un worker ; transmettre les résultats à l'interface par signaux/slots ou par l'adaptateur existant.
- Protéger les secrets : conserver le jeton du serveur en mémoire et ne pas le journaliser ni l'écrire dans `config.json`.
- Ne pas toucher aux corps des fonctions QSS ni aux références de tests AST/QSS sans nécessité démontrée et validation correspondante.
- Éviter toute modification des dépendances, du packaging et des chemins de lancement dans les premiers lots si elle n'est pas indispensable.

## 4. Architecture cible proposée

Conserver initialement les chemins existants. Introduire les frontières logiques suivantes **au sein de l'arborescence réelle**, puis seulement envisager une migration physique des packages :

```text
main.pyw                  point d'entrée inchangé
src/app/                  composition, démarrage, arrêt, injection des services
src/application/          cas d'usage : conversation, documents, actions, voix
src/domain/               modèles et règles indépendants de Qt et des I/O
src/llm/                  adaptateur client/serveur llama.cpp existant
src/documents/            adaptateurs PDF, images et analyse existants
src/tts/                  adaptateur Kokoro existant
src/config/               persistance et validation de configuration
src/ui/                   fenêtres, widgets, thèmes, adaptateurs Qt
core/                    skills existants, sans déplacement initial
```

**Sens autorisé des dépendances** : `ui -> application -> domain` ; `app` assemble les implémentations concrètes ; `llm`, `documents`, `tts`, `config` et `core` fournissent les adaptateurs nécessaires. Ne pas forcer un service unique à gérer conversation, documents, audio et configuration. Introduire une abstraction seulement lorsqu'elle sépare effectivement une dépendance ou facilite un test.

### 4.1 Contrats à établir après inspection du code

- `ConversationRequest` : texte, historique utile, pièces jointes et options réellement nécessaires ; éviter de dupliquer les structures déjà utilisées.
- `ConversationEvent` : événement typé de début, fragment, appel d'outil, résultat, fin, erreur ou annulation, uniquement pour les événements effectivement produits.
- `ConversationService` : orchestration d'une requête et de son cycle de vie ; ne connaît ni fenêtre ni widget.
- `LlmGateway` : contrat minimal pour lancer/consommer/annuler une réponse ; adaptateur vers le client existant, sans remplacer prématurément `LlamaThread`.
- `DocumentGateway`, `SpeechGateway` et `ConfigRepository` : contrats facultatifs, à introduire seulement si le parcours traité en a besoin.
- `TaskHandle` ou mécanisme d'annulation existant : définit le propriétaire de la tâche et la manière d'en demander l'arrêt ; vérifier la sémantique effective des threads et requêtes avant de choisir l'API.

Choisir des noms conformes à `NAMING_CONVENTION.md`. Définir les types à la frontière application/adaptateur ; éviter de passer un `QWidget` ou une fenêtre entière comme dépendance d'un service. Les signaux Qt sont gérés par une couche de liaison Qt, pas par les modèles du domaine.

### 4.2 Point de composition

`src/app/application.py` doit créer les composants concrets, injecter leurs dépendances et coordonner leur fermeture. Les fenêtres reçoivent les cas d'usage nécessaires ou un adaptateur Qt fin. Les services ne créent pas eux-mêmes leurs fenêtres ni ne récupèrent leur configuration dans une variable globale. Préserver `main.pyw` comme point d'entrée tant que le lancement Windows n'a pas été revalidé.

## 5. Procédure impérative, lot par lot

### Lot 0 : établir l'état réel et une base de référence

1. Vérifier la présence des patchs annoncés et identifier les imports circulaires, accès à des attributs de fenêtres depuis les contrôleurs, instanciations directes de clients LLM et création/arrêt des threads.
2. Tracer le parcours **saisie utilisateur -> requête LLM -> fragments de réponse -> rendu -> fin/annulation** avec noms de méthodes et fichiers réellement trouvés.
3. Relever les commandes de lancement, les tests existants et leurs résultats initiaux. Ne pas corriger silencieusement une panne préexistante : la consigner.
4. Dresser une carte concise : composant, responsabilité actuelle, dépendances entrantes/sortantes, propriétaire du cycle de vie, tests disponibles.
5. Choisir une seule extraction à faible risque. Si le flux LLM est déjà correctement séparé, choisir un autre flux sur preuve tirée du code.

**Critère de sortie** : une proposition de modifications reliée aux fichiers réels, avec tests de référence et risques connus.

### Lot 1 : isoler le parcours conversationnel

1. Ajouter des tests de caractérisation pour une réponse complète, un flux de fragments, une erreur, une annulation et la fermeture pendant une réponse, selon les capacités réelles de l'application.
2. Extraire l'orchestration de la requête depuis la fenêtre ou le contrôleur concerné vers un service applicatif. Garder la construction des widgets et le rendu dans `src/ui/`.
3. Adapter le client existant via un contrat minimal. Injecter un faux client dans les tests du service ; ne pas lancer `llama-server.exe` pour ces tests.
4. Laisser les méthodes publiques historiques comme façades de délégation lorsque des appels existants en dépendent.
5. Vérifier l'ordre des fragments, le résultat final, les erreurs, l'absence de doublons et la possibilité d'annuler sans mettre à jour une fenêtre détruite.

**Critère de sortie** : service testable sans PySide6 pour la logique pure ; comportement UI inchangé ; tests ciblés et régressions existantes passants, ou écarts documentés.

### Lot 2 : expliciter le cycle de vie asynchrone

1. Identifier le propriétaire de chaque opération : LLM, analyse documentaire, capture audio, TTS, surveillance et serveur.
2. Définir les états et transitions nécessaires : créée, active, annulation demandée, terminée ou en erreur. Ne pas imposer une machine à états supplémentaire si l'existant couvre déjà ces cas.
3. Faire converger l'arrêt de l'application vers un orchestrateur unique : empêcher de nouvelles tâches, demander l'annulation, attendre la fin avec la stratégie appropriée, puis libérer les ressources.
4. Tester le cas « fermer pendant une réponse » et « fermer pendant l'analyse d'un document » sans `QThread` encore actif ni callback vers une fenêtre détruite.

**Critère de sortie** : responsabilités de fermeture documentées et tests correspondants ; validation native Windows requise avant de déclarer l'arrêt entièrement validé.

### Lot 3 : étendre seulement si le premier flux est stabilisé

Appliquer le même principe aux documents, puis à la voix et aux actions, un domaine à la fois. Préserver le rendu des vignettes, les commandes slash, les règles de thème, les skills et leurs points d'entrée. Ne pas créer une interface générique commune à des flux dont les comportements diffèrent.

### Lot 4 : harmoniser les packages, en option et séparément

Après stabilisation fonctionnelle, décider si un package nommé sous `src/` et le déplacement de `core/` apportent un bénéfice réel. Si oui, préparer `pyproject.toml`, installation éditable, migration des imports, lancement `main.pyw`, découverte des skills, chemins des ressources et scripts MCP. Faire cette migration dans un lot distinct. Ne pas présenter la structure proposée comme une obligation immédiate : le changement de disposition peut modifier les conditions d'import et de lancement.

## 6. Stratégie de tests et de validation

### Tests à ajouter ou conserver

- Unitaires sans GUI : cas d'usage avec faux adaptateurs ; streaming ordonné ; erreur ; annulation ; historique et pièces jointes si concernés.
- Intégration Qt : signaux reçus sur le bon objet, fenêtre fermée sans mise à jour tardive, arrêt des workers ; n'exécuter ces tests que dans un environnement approprié.
- Non-régression : tests d'extraction documentaire, paramètres et stylesheet ; vérifier que les références AST/QSS restent pertinentes après modification.
- Parcours manuels Windows : démarrage via `main.pyw` et raccourci, dialogue documentaire, thèmes, raccourcis clavier, audio, TTS, skills et fermeture, selon les composants réellement disponibles.

Depuis la racine du projet Windows, utiliser l'interpréteur du README lorsque présent :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Lancer également les tests ciblés du lot. Noter pour chaque commande : environnement, résultat, échecs préexistants, échecs nouveaux et validations impossibles. Un test statique réussi ne prouve pas que l'application complète fonctionne sous Windows.

## 7. Conditions d'acceptation générales

- Les frontières de dépendances sont respectées ; les services applicatifs ne dépendent pas des widgets.
- Les dépendances sont visibles à la construction des composants concernés.
- Le comportement externe et les points d'entrée documentés restent compatibles.
- Les nouveaux cas d'usage sont testables avec des doublures, sans matériel ni serveur LLM.
- Les tâches longues ont un propriétaire et un arrêt définis ; aucune mise à jour de widget depuis un worker.
- Les règles de sécurité existantes, notamment l'authentification locale en mémoire, restent intactes.
- Les tests ajoutés démontrent le comportement, et non seulement l'existence de fichiers ou de méthodes.
- Le README, les règles d'architecture et les audits sont mis à jour uniquement pour décrire l'état **effectivement implémenté**.

## 8. Format de restitution obligatoire de l'agent

À la fin de chaque lot, rendre :

1. **Constat vérifié** : fichiers inspectés, flux réel et problèmes confirmés ; distinguer constat et hypothèse.
2. **Modifications** : fichiers changés, responsabilité déplacée et compatibilité maintenue.
3. **Tests** : nouveaux cas, commandes exécutées et résultats exacts.
4. **Limites** : éléments non testés, dépendances matérielles/Windows et risques résiduels.
5. **Suite proposée** : prochain lot limité, sans annoncer comme terminées des modifications non réalisées.

Ne pas annoncer « architecture terminée » tant que les parcours principaux et la validation native n'ont pas été vérifiés.

## 9. Instruction prête à donner à l'agent

> Lis `AGENTS.md`, le README, les conventions et les audits présents. Applique le présent guide en commençant par le lot 0, puis implémente uniquement le premier lot pertinent et vérifiable. Inspecte le code réel avant de définir les contrats ; préserve les façades, le point d'entrée et les comportements existants. Ajoute les tests de caractérisation et de non-régression, exécute les validations disponibles et rapporte honnêtement ce qui n'a pas pu être vérifié. Ne déplace pas tous les packages et ne refonds pas l'UI en même temps que l'extraction métier.

## 10. Références de conception

- README du projet fourni : arborescence annoncée, patchs, règles de développement et commandes de tests.
- Documentation officielle Qt for Python : `QThread`, communication signaux/slots et règles d'utilisation des widgets depuis le thread principal.
- Python Packaging User Guide : différence entre disposition `src` et disposition à plat, et conséquences sur les imports et l'installation éditable.

---

### Explication des choix rédactionnels

Le guide distingue l'état documenté de l'état réel à vérifier, transforme l'objectif architectural en lots testables et évite qu'un agent modifie simultanément les flux métier, les imports et le lancement Windows. Les critères d'acceptation et le format de restitution rendent chaque changement vérifiable.
