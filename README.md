# Assistant IA Local (Architecture Modulaire)

Assistant IA local sous Windows propulsé par **llama.cpp** (modèles GGUF avec accélération CUDA) et **Kokoro TTS** (synthèse vocale locale ONNX/CUDA), doté d'une interface graphique native PySide6 fluide avec effets acryliques Windows 11.

---

## 🌟 Points Forts de la Nouvelle Architecture

L'application a été entièrement refactorisée selon le principe de responsabilité unique (**Single Responsibility Principle**) :
- **Architecture Découplée** : Séparation stricte entre le backend (serveur llama.cpp, TTS, threads asynchrones, surveillance matérielle) et l'interface graphique (fenêtres, widgets réutilisables, thème).
- **Code Lisible et Maintenable** : Passage d'un fichier monolithique de plus
  de 6 700 lignes à une architecture par domaines sous `src/`. Les modules
  sont regroupés par responsabilité ; les contrôleurs UI complexes restent des
  orchestrateurs volumineux et leur découpage incrémental est suivi dans
  [MAINTAINABILITY_AUDIT.md](MAINTAINABILITY_AUDIT.md).
- **Robustesse & Performance Accrues** :
  - `KokoroEngine` persistant avec import fainéant (*lazy loading*) d'ONNX Runtime (W-12).
  - Nettoyage automatique des fichiers temporaires (vignettes PDF, captures haute définition) lors de la fermeture (W-15).
  - Limitation de l'historique documentaire à 10 échanges (20 messages) pour éviter la saturation du contexte VRAM/LLM (W-19).
  - Délais de scrutation presse-papiers optimisés pour éviter tout gel de l'UI (W-13).
- **Compatibilité Windows** : le raccourci `Assistant IA.lnk` lance
  `main.pyw` avec l'interpréteur `.venv` ; le même point d'entrée est utilisé
  par les commandes documentées ci-dessous.

---

## 📁 Arborescence du Projet

```text
Assistant/
│
├── main.pyw                       # Point d'entrée principal moderne (< 40 lignes)
├── config.json                    # Configuration persistante (actions, llama, voix, TTS)
├── requirements.txt               # Runtime commun
├── requirements-ui.txt            # GUI, audio, TTS et accélération ONNX/CUDA
├── requirements-skills.txt        # Skills bureautiques optionnels
├── requirements-dev.txt           # Environnement complet + outils qualité
├── assistant_icon.webp            # Icône officielle de l'application
│
├── src/                           # Code source modulaire
│   ├── app/                       # Cycle de vie et gestionnaires globaux
│   │   ├── application.py         # Orchestrateur d'application
│   │   └── hotkey_managers.py     # Raccourcis clavier (Ctrl+., Ctrl+1-9, Ctrl+Alt+1-9)
│   │
│   ├── config/                    # Schéma et persistance
│   │   ├── schema.py              # Valeurs par défaut, constantes et journalisation
│   │   └── manager.py             # Chargement et sauvegarde atomique de config.json
│   │
│   ├── platform/                  # Intégration Windows
│   │   ├── dll_loader.py          # Détection et injection des DLLs CUDA / cuDNN
│   │   └── foreground.py          # Détection de l'application active (Adobe Acrobat, etc.)
│   │
│   ├── audio/                     # Capture et traitement du signal
│   │   └── recorder.py            # AudioRecorderThread (SoundDevice, RMS, rééchantillonnage)
│   │
│   ├── tts/                       # Synthèse vocale locale
│   │   ├── engine.py              # KokoroEngine (Singleton CUDA persistant)
│   │   └── thread.py              # KokoroWarmupThread, KokoroTtsThread
│   │
│   ├── llm/                       # Interaction avec le grand modèle de langage
│   │   ├── server_manager.py      # Supervision du processus llama-server.exe
│   │   ├── response_parser.py     # Nettoyage de flux, balises <think>, parsing audio
│   │   ├── agent.py               # Détection des appels d'outils et termes d'action
│   │   └── client.py              # LlamaThread (requêtes streaming SSE)
│   │
│   ├── documents/                 # Analyse de documents locaux (PDF / Images)
│   │   ├── pdf_utils.py           # Extraction de texte et navigation PyMuPDF
│   │   ├── payload_builder.py     # Encodage base64 et formatage multimodal
│   │   └── thread.py              # DocumentAnalysisThread
│   │
│   ├── rendering/                 # Rendu et conversion
│   │   └── markdown.py            # Markdown vers HTML et vers texte oralisé
│   │
│   ├── monitoring/                # Surveillance matérielle
│   │   ├── server_status.py       # Ping HTTP de llama-server
│   │   ├── nvidia_status.py       # nvidia-smi (VRAM, température, P-State)
│   │   └── runtime_info.py        # CPU, RAM, threads, modèle actif
│   │
│   └── ui/                        # Interface graphique PySide6
│       ├── design_tokens.py       # Couleurs et dimensions par thème
│       ├── stylesheet.py           # Helpers QSS réutilisables
│       ├── stylesheet_document.py  # QSS des fenêtres documentaires
│       ├── theme.py               # Acrylique Windows 11 et application du thème
│       ├── icons.py               # Registre vectoriel SVG
│       ├── status_formatters.py   # Titres et durées des blocs d'activité
│       ├── tray.py                # Icône de la zone de notification Windows (systray)
│       ├── widgets/               # Composants graphiques réutilisables
│       │   ├── audio_bars.py      # Barres de visualisation sonore animées
│       │   ├── animated_buttons.py# Boutons interactifs avec animations vectorielles
│       │   ├── attachment_widget.py# Prévisualisation des pièces jointes
│       │   ├── chat_bubble.py     # Bulles de dialogue et loupe interactive
│       │   ├── message_editor.py  # Éditeur de requête avec support du glisser-déposer
│       │   ├── recording_indicator.py# Indicateur flottant d'écoute vocale
│       │   ├── thinking_dots.py   # Animation des points de réflexion
│       │   └── document_attachment_preview.py # Aperçu et plages de pages PDF
│       │   └── timeline_header.py  # En-têtes repliables de timeline
│       │   └── tool_call_step.py   # Étape individuelle d'appel d'outil
│       └── windows/               # Fenêtres principales
│           ├── assistant_window.py# Fenêtre principale flottante de réponse
│           ├── assistant_response_renderer.py # Rendu HTML et streaming assistant
│           ├── document_dialog.py # Fenêtre d'analyse documentaire interactive (Ctrl+9)
│           ├── document_composer_controller.py # Envoi, historique et microphone
│           ├── document_conversation_renderer.py # Rendu conversationnel et viewport
│           ├── document_source_renderer.py # Captures et liens des sources
│           ├── document_response_controller.py # Streaming et cycle de réponse
│           ├── settings_dialog.py # Fenêtre des paramètres complets
│           ├── runtime_info_dialog.py # Diagnostic matériel et logiciel
│           └── settings_tabs.py    # Builder des onglets de configuration
│
└── core/                          # Gestionnaire de compétences bureautiques
    ├── skill_manager.py           # Détection et exécution des skills
    └── skills/                    # Modules DOCX, XLSX, PDF, PPTX
```

---

## 🎨 Règles de cohérence UI

Les règles obligatoires pour centraliser les couleurs, dimensions, icônes,
styles QSS et composants réutilisables sont documentées dans
[UI_DESIGN_RULES.md](UI_DESIGN_RULES.md).

Chaque skill peut déclarer une icône locale dans sa classe avec `icon = "icon.svg"`
ou `icon = "icon.png"`. Le fichier est recherché dans le dossier du skill.
Toute modification visuelle doit également respecter la checklist de validation
des thèmes, états interactifs, accessibilité et assets décrite dans ce document.
L'audit de conformité des règles, thèmes et contrôles est disponible dans
[UI_CONFORMANCE_AUDIT.md](UI_CONFORMANCE_AUDIT.md).
L'état détaillé de l'harmonisation visuelle est disponible dans
[UI_VISUAL_HARMONIZATION_AUDIT.md](UI_VISUAL_HARMONIZATION_AUDIT.md).
La checklist de validation native Windows est disponible dans
[UI_WINDOWS_RELEASE_CHECKLIST.md](UI_WINDOWS_RELEASE_CHECKLIST.md).
L'audit de maintenabilité et de facilité de mise à jour est disponible dans
[MAINTAINABILITY_AUDIT.md](MAINTAINABILITY_AUDIT.md).
La synthèse à jour de ces audits est disponible dans
[AUDIT_GLOBAL.md](AUDIT_GLOBAL.md). Ce rapport global est le document de
référence pour le verdict, les résultats de validation et la roadmap restante ;
les trois rapports spécialisés conservent le détail de chaque domaine.

---

## 🧩 Skills & Serveur MCP (Model Context Protocol)

Les skills de l'assistant reposent sur **FastMCP** ([Model Context Protocol](https://modelcontextprotocol.io/)). Ils sont découverts automatiquement et utilisables à la fois en local (via `llama.cpp` et l'interface Ctrl+9) et par des clients externes (Claude Desktop, Cursor, Antigravity, etc.).

- **Guide complet de création de skills pour IA et développeurs** : [skills/README.md](skills/README.md).
- **Skills disponibles** : `pdf`, `docx`, `excel`, `pptx`, `ftnc`.
- **Serveur MCP standard pour applications tierces** :
  ```powershell
  # Lancement du serveur MCP en mode stdio
  .\.venv\Scripts\python.exe scripts/run_mcp_server.py
  ```

## 🚀 Installation & Démarrage

### Authentification locale de llama-server

Lorsque l'application démarre `llama-server`, elle génère un jeton
cryptographiquement aléatoire en mémoire et le transmet via `--api-key`.
Les requêtes d'inférence et de supervision utilisent automatiquement ce jeton
dans l'en-tête `Authorization: Bearer ...`. Le jeton n'est pas écrit dans
`config.json` ni dans `llama-server.log` et il est renouvelé à chaque
redémarrage du serveur.

Un serveur `llama-server` lancé manuellement en dehors de l'application n'est
pas compatible avec ce mode d'authentification automatique. Il doit être
arrêté puis relancé par l'application, ou configuré séparément avec son propre
jeton.

### 1. Prérequis
- Windows 10/11 64-bit
- Python 3.10 ou supérieur
- (Optionnel mais recommandé) Carte graphique NVIDIA avec support CUDA 12.x

### 2. Installation des Dépendances
Dans un terminal PowerShell :
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-skills.txt
```

Pour préparer un environnement complet de développement et de validation :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements.txt` contient uniquement le socle runtime commun. Les profils
séparés évitent d'installer PySide6, l'audio, CUDA/ONNX ou les skills lors d'un
simple usage backend ou d'un audit ciblé. La version `onnxruntime-gpu==1.19.2`
reste volontairement épinglée ; ne pas installer simultanément le paquet CPU
`onnxruntime`.

### 3. Lancement
Le point d'entrée unique de l'application est :
```powershell
.\.venv\Scripts\python.exe main.pyw
```
Le raccourci Windows `Assistant IA.lnk` utilise cette même commande.

À la fermeture via le menu **Quitter** ou l’icône de notification, l’application
demande l’arrêt des threads LLM, documentaires, audio, TTS et monitoring puis
attend leur terminaison avant de quitter Qt. Cette séquence évite la destruction
d’un `QThread` encore actif.

---

## ⌨️ Raccourcis Clavier Globaux

| Raccourci | Fonction |
| :--- | :--- |
| **`Ctrl + .`** | Ouvre le menu contextuel flottant avec les actions configurées. |
| **`Ctrl + 1` .. `Ctrl + 8`** | Déclenche directement l'action configurée n° 1 à 8 sur le texte sélectionné. |
| **`Ctrl + 9`** | Ouvre l'interface de **Dialogue et Analyse Documentaire** (PDF / Images). |
| **`Ctrl + Alt + 1` .. `Ctrl + Alt + 9`** | Dictée vocale directe : maintenez enfoncé pour enregistrer, relâchez pour envoyer. |
| **`Échap`** | Ferme la fenêtre active ou annule l'enregistrement vocal en cours. |

---

## 🛠️ Schéma des Flux et Services

```mermaid
graph TD
    User([Utilisateur / Clavier / Voix]) --> Hotkeys[src/app/hotkey_managers.py]
    Hotkeys --> Assistant[src/ui/windows/assistant_window.py]
    Hotkeys --> DocDialog[src/ui/windows/document_dialog.py]
    
    Assistant --> LlamaClient[src/llm/client.py]
    DocDialog --> DocThread[src/documents/thread.py]
    
    LlamaClient --> LlamaServer[llama-server.exe / CUDA]
    DocThread --> LlamaServer
    
    Assistant --> TTS[src/tts/engine.py (Kokoro)]
    Assistant --> Monitor[src/monitoring/runtime_info.py]
    Monitor --> Nvidia[src/monitoring/nvidia_status.py]
```

---

## 🤖 Gouvernance & Développement par LLM

Le projet applique une règle stricte pour toute contribution ou intervention par un modèle d'IA (LLM / Agent de programmation) :
- **Règles obligatoires** : consulter le document de référence [`AGENTS.md`](AGENTS.md) ou `.agents/rules/llm_development_rules.md`.
- **Exigences** :
  1. À chaque action, la **documentation**, les **tests unitaires**, et les **sources uniques de vérité** (*Design Tokens*, icônes SVG dans `src/ui/icons.py`) doivent être mis à jour.
  2. Aucun bug ne peut être résolu sans test de non-régression associé.
  3. Tous les tests doivent passer au vert avant livraison (`python -m unittest discover tests`).

---

## 🔌 Serveur MCP Standard (Model Context Protocol)

L'ensemble des compétences de l'assistant (création Word, Excel, PDF, PowerPoint, FTNC) est exposé via le protocole standard MCP :
```powershell
.\.venv\Scripts\python.exe scripts/run_mcp_server.py
```
Voir [`skills/README.md`](skills/README.md) pour les détails d'intégration avec Claude Desktop ou Cursor.
