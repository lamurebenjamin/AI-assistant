# -*- coding: utf-8 -*-
"""Constantes et schéma par défaut de la configuration de l'assistant."""

import copy
import logging
import os
from pathlib import Path

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
HTTP_TIMEOUT = (10, 60)
STATUS_TIMEOUT = (1.5, 2.5)
LOGGER = logging.getLogger("Assistant")
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

DEFAULT_CONFIG = {
    "hotkeys_enabled": True,
    "api_url": "http://127.0.0.1:8080/v1/chat/completions",
    "llama_server": {
        "auto_start": True,
        "executable": "llama-server.exe",
        "model": "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        "arguments": [
            "--mmproj", "mmproj-F16.gguf",
            "--spec-draft-model", "mtp-gemma-4-12B-it.gguf",
            "--spec-type", "draft-mtp",
            "--spec-draft-n-max", "4",
            "--n-gpu-layers", "999",
            "--ctx-size", "8192",
            "--port", "8080",
            "--flash-attn", "on",
            "--parallel", "1",
            "--cache-type-k", "q8_0",
            "--cache-type-v", "q8_0",
            "--spec-draft-type-k", "q8_0",
            "--spec-draft-type-v", "q8_0",
            "--reasoning-budget", "0",
            "-b", "512",
            "--temp", "1.0",
            "--top-p", "0.95",
            "--top-k", "64",
            "--jinja",
        ],
    },
    "text_to_speech": {
        "rate": 0,
        "speed": 1.2,
        "max_pause_ms": 220,
        "volume": 100,
        "automatic_reading": False,
        "model_path": os.path.join("kokoro", "kokoro-v1.0.onnx"),
        "voices_path": os.path.join("kokoro", "voices-v1.0.bin"),
        "voice": "ff_siwis",
        "language": "fr-fr",
        "output_device": None,
        "output_device_name": "",
    },
    "voice_input": {
        "enabled": True,
        "hotkey": "ctrl+alt+1",
        "input_device": None,
        "input_device_name": "",
        "sample_rate": 16000,
        "minimum_duration": 0.5,
        "minimum_rms_level": 0.003,
        "audio_format": "wav",
        "maximum_duration": 60.0,
        "release_tail_ms": 700,
        "microphone_gain": 2.0,
        "language": "fr",
        "vocabulary_prompt": (
            "Français technique. Vocabulaire possible : Safran, roue frein, "
            "éléments finis, contrainte, Kevin, Valentin, ATL2, Falcon 2000, Falcon 2000EX, Falcon 900/900EX, "
            "déformation, fatigue, dimensionnement, CATIA, ANSIS, Rafale Air, Rafale Marine, Mirage 2000, Mirage F1"
        ),
    },
    "actions": [
        {
            "name": "Répondre",
            "system_prompt": "Tu es un assistant IA utile. Réponds de manière concise et directe à la question ou au texte de l'utilisateur.",
            "prompt_prefix": "",
        },
        {
            "name": "Améliorer",
            "system_prompt": "Tu es un expert en rédaction. Réécris le texte de l'utilisateur pour l'améliorer (orthographe, clarté, style). Ne renvoie que le texte réécrit, sans commentaires.",
            "prompt_prefix": "Réécris ce texte :",
        },
        {
            "name": "Agent",
            "system_prompt": (
                "Tu es un agent IA local. Tu peux répondre normalement, mais tu peux aussi utiliser les outils "
                "qui te sont fournis. Utilise un outil lorsque la demande nécessite réellement une action, "
                "par exemple créer un fichier. Ne simule jamais l'exécution d'un outil : si un outil est nécessaire, "
                "appelle-le. Après l'exécution, explique brièvement le résultat à l'utilisateur. "
                "Réponds en français sauf demande contraire."
            ),
            "prompt_prefix": "",
        },
    ],
}
