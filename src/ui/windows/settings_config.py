"""Validation et normalisation des valeurs éditées dans SettingsDialog."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.config.schema import DEFAULT_CONFIG


def normalize_api_url(value: Any) -> str:
    """Retourne une URL API valide, ou celle par défaut si la valeur est vide."""
    candidate = str(value or "").strip()
    if candidate.startswith(("http://", "https://")):
        return candidate
    return DEFAULT_CONFIG["api_url"]


def normalize_server_config(
    auto_start: Any,
    executable: Any,
    model: Any,
    arguments: Any,
) -> dict[str, Any]:
    """Normalise les champs édités du serveur local sans modifier l'entrée."""
    raw_arguments = arguments if isinstance(arguments, list) else []
    normalized_arguments = [
        str(argument).strip()
        for argument in raw_arguments
        if str(argument).strip()
    ]
    return {
        "auto_start": bool(auto_start),
        "executable": str(executable or "").strip(),
        "model": str(model or "").strip(),
        "arguments": normalized_arguments,
    }


def copy_server_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Prépare une copie éditable de la configuration serveur."""
    source = config if isinstance(config, Mapping) else {}
    arguments = source.get("arguments", [])
    if not isinstance(arguments, list):
        arguments = []
    return normalize_server_config(
        source.get("auto_start", True),
        source.get("executable", "llama-server.exe"),
        source.get("model", ""),
        arguments,
    )
