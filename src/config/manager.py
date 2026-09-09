# -*- coding: utf-8 -*-
"""Gestionnaire de chargement et de sauvegarde de la configuration JSON."""

import copy
import json
import os
import re
from typing import Optional

from src.config.schema import CONFIG_FILE, DEFAULT_CONFIG, LOGGER


def load_config(path: Optional[str] = None) -> dict:
    """Charge et normalise la configuration sans bloquer le démarrage."""
    target_path = path or CONFIG_FILE
    config = copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(target_path):
        return config

    try:
        with open(target_path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
        if not isinstance(loaded, dict):
            raise ValueError("La racine de la configuration doit être un objet JSON")

        config["hotkeys_enabled"] = bool(loaded.get("hotkeys_enabled", True))

        loaded_tts = loaded.get("text_to_speech")
        if isinstance(loaded_tts, dict):
            config["text_to_speech"].update(loaded_tts)
        tts = config["text_to_speech"]
        tts["rate"] = int(tts.get("rate", 0))
        tts["volume"] = min(100, max(0, int(tts.get("volume", 100))))
        tts["automatic_reading"] = bool(tts.get("automatic_reading", False))

        # Migration automatique depuis l'ancienne configuration Piper
        old_model_path = str(tts.get("model_path", "")).lower()
        if "piper" in old_model_path or old_model_path.endswith("fr_fr-siwis-medium.onnx"):
            tts["model_path"] = DEFAULT_CONFIG["text_to_speech"]["model_path"]
        tts.pop("piper_executable", None)
        tts.setdefault("voices_path", DEFAULT_CONFIG["text_to_speech"]["voices_path"])
        tts.setdefault("voice", DEFAULT_CONFIG["text_to_speech"]["voice"])
        tts.setdefault("language", DEFAULT_CONFIG["text_to_speech"]["language"])
        tts.setdefault("output_device", DEFAULT_CONFIG["text_to_speech"]["output_device"])
        tts.setdefault("output_device_name", DEFAULT_CONFIG["text_to_speech"]["output_device_name"])

        api_url = loaded.get("api_url", config["api_url"])
        if not isinstance(api_url, str) or not re.match(r"^https?://", api_url.strip()):
            api_url = config["api_url"]
        if api_url in {
            "http://localhost:8080/completion",
            "http://127.0.0.1:8080/completion",
        }:
            api_url = DEFAULT_CONFIG["api_url"]
        config["api_url"] = api_url.strip()

        loaded_server = loaded.get("llama_server")
        if isinstance(loaded_server, dict):
            config["llama_server"].update(loaded_server)
        server = config["llama_server"]
        server["auto_start"] = bool(server.get("auto_start", True))
        for key in ("executable", "model"):
            if not isinstance(server.get(key), str):
                server[key] = DEFAULT_CONFIG["llama_server"][key]
        arguments = server.get("arguments")
        if not isinstance(arguments, list) or not all(
            isinstance(argument, (str, int, float)) for argument in arguments
        ):
            server["arguments"] = copy.deepcopy(
                DEFAULT_CONFIG["llama_server"]["arguments"]
            )

        # Déduplication des arguments tout en préservant l'ordre
        deduped_args = []
        seen_flags = set()
        i = 0
        while i < len(server["arguments"]):
            arg = str(server["arguments"][i])
            if arg.startswith("-") and arg in seen_flags and not arg.startswith("--"):
                # ex: -b duplicata
                i += 1
                if i < len(server["arguments"]) and not str(server["arguments"][i]).startswith("-"):
                    i += 1
                continue
            deduped_args.append(server["arguments"][i])
            i += 1

        # Assurer que --jinja est présent une seule fois
        if "--jinja" not in [str(a) for a in deduped_args]:
            deduped_args.append("--jinja")
        else:
            # Retirer d'éventuels doublons de --jinja
            first = True
            final_args = []
            for a in deduped_args:
                if str(a) == "--jinja":
                    if first:
                        final_args.append(a)
                        first = False
                else:
                    final_args.append(a)
            deduped_args = final_args

        server["arguments"] = deduped_args

        loaded_voice = loaded.get("voice_input")
        if isinstance(loaded_voice, dict):
            config["voice_input"].update(loaded_voice)
        voice = config["voice_input"]
        voice["enabled"] = bool(voice.get("enabled", True))
        voice["hotkey"] = "ctrl+alt+1"
        voice["input_device"] = voice.get("input_device")
        voice["input_device_name"] = str(voice.get("input_device_name") or "")
        voice["sample_rate"] = int(voice.get("sample_rate") or 16000)
        voice["minimum_duration"] = max(0.1, float(voice.get("minimum_duration") or 0.5))
        voice["minimum_rms_level"] = max(0.0, float(voice.get("minimum_rms_level", 0.003)))
        voice["audio_format"] = "wav"
        voice["maximum_duration"] = min(300.0, max(1.0, float(voice.get("maximum_duration") or 60.0)))
        voice["release_tail_ms"] = min(1500, max(0, int(voice.get("release_tail_ms", 700))))
        voice["microphone_gain"] = min(8.0, max(1.0, float(voice.get("microphone_gain", 2.0))))
        voice["language"] = str(voice.get("language") or "fr").strip().lower()
        voice["vocabulary_prompt"] = str(
            voice.get("vocabulary_prompt") or DEFAULT_CONFIG["voice_input"]["vocabulary_prompt"]
        ).strip()

        # Migration automatique des anciens réglages de seuil
        if isinstance(loaded_voice, dict):
            if loaded_voice.get("minimum_duration") == 0.3:
                voice["minimum_duration"] = 0.5
            if loaded_voice.get("minimum_rms_level") == 0.0001:
                voice["minimum_rms_level"] = 0.003
            if loaded_voice.get("release_tail_ms") == 300:
                voice["release_tail_ms"] = 700

        loaded_actions = loaded.get("actions")
        valid_actions = []
        if isinstance(loaded_actions, list):
            for action in loaded_actions:
                if not isinstance(action, dict):
                    continue
                name = action.get("name")
                system_prompt = action.get("system_prompt")
                prompt_prefix = action.get("prompt_prefix", "")
                if isinstance(name, str) and isinstance(system_prompt, str):
                    clean_name = name.strip()
                    # Filtre les actions vides / placeholders
                    if clean_name and clean_name != "Action sans nom" or system_prompt.strip():
                        valid_actions.append({
                            "name": clean_name or "Action sans nom",
                            "system_prompt": system_prompt,
                            "prompt_prefix": (
                                prompt_prefix if isinstance(prompt_prefix, str) else ""
                            ),
                        })
        config["actions"] = valid_actions or copy.deepcopy(DEFAULT_CONFIG["actions"])
        # Ajoute automatiquement l'action Agent si absente
        if not any(str(action.get("name", "")).strip().casefold() == "agent" for action in config["actions"]):
            config["actions"].append(copy.deepcopy(DEFAULT_CONFIG["actions"][-1]))
        return config
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        LOGGER.warning("Configuration ignorée (%s): %s", target_path, error)
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict, path: Optional[str] = None) -> None:
    """Enregistre la configuration de façon atomique."""
    target_path = path or CONFIG_FILE
    temporary_file = target_path + ".tmp"
    try:
        with open(temporary_file, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=4, ensure_ascii=False)
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(temporary_file, target_path)
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temporary_file)
        except FileNotFoundError:
            pass
        raise
