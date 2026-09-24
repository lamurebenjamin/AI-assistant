"""Constantes et schéma par défaut de la configuration de l'assistant."""

import logging
import os
from typing import TypedDict


class ActionConfig(TypedDict):
    name: str
    system_prompt: str
    prompt_prefix: str


class LlamaServerConfig(TypedDict):
    auto_start: bool
    executable: str
    model: str
    arguments: list[str | int | float]


class TextToSpeechConfig(TypedDict):
    rate: int
    speed: float
    max_pause_ms: int
    volume: int
    automatic_reading: bool
    model_path: str
    voices_path: str
    voice: str
    language: str
    output_device: int | None
    output_device_name: str


class VoiceInputConfig(TypedDict):
    enabled: bool
    hotkey: str
    input_device: int | None
    input_device_name: str
    sample_rate: int
    minimum_duration: float
    minimum_rms_level: float
    audio_format: str
    maximum_duration: float
    release_tail_ms: int
    microphone_gain: float
    language: str
    vocabulary_prompt: str


class Ctrl9Config(TypedDict):
    width: int
    max_height: int
    font_size: int


class FtncConfig(TypedDict, total=False):
    fichier_ftnc: str
    feuille_ftnc: str
    fichier_suivi_euro: str
    feuille_suivi_euro: str


class SkillsConfig(TypedDict, total=False):
    ftnc: FtncConfig


class AssistantConfig(TypedDict, total=False):
    theme: str
    hotkeys_enabled: bool
    api_url: str
    llm_max_tokens: int
    llama_server: LlamaServerConfig
    text_to_speech: TextToSpeechConfig
    voice_input: VoiceInputConfig
    actions: list[ActionConfig]
    ctrl9: Ctrl9Config
    skills: SkillsConfig

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
HTTP_TIMEOUT = (10, 60)
STATUS_TIMEOUT = (1.5, 2.5)
LOGGER = logging.getLogger("Assistant")
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

DEFAULT_CONFIG = {
    "theme": "dark",
    "hotkeys_enabled": True,
    "api_url": "http://127.0.0.1:8080/v1/chat/completions",
    "llm_max_tokens": 8192,
    "skills": {
        "ftnc": {
            "fichier_ftnc": "",
            "feuille_ftnc": "Données consolidées",
            "fichier_suivi_euro": "",
            "feuille_suivi_euro": "SUIVI",
        }
    },
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
    "ctrl9": {
        "width": 480,
        "max_height": 620,
        "font_size": 14,
    },
}
