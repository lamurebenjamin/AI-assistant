# -*- coding: utf-8 -*-
"""Logique décisionnelle de l'Agent IA pour l'appel et l'exécution d'outils."""

import re
from typing import List, Tuple

# Termes déclencheurs d'actions et d'artefacts
ACTION_TERMS: Tuple[str, ...] = (
    "crée",
    "créer",
    "créé",
    "génère",
    "générer",
    "produis",
    "produire",
    "fabrique",
    "fais-moi",
    "fais un",
    "prépare",
    "rédige",
    "résume",
    "résumer",
    "synthétise",
    "synthétiser",
    "synthèse",
    "enregistre",
    "sauvegarde",
    "exporte",
    "convertis",
    "construis",
    "transforme",
    "modifie le fichier",
    "mets à jour le fichier",
)

ARTIFACT_TERMS: Tuple[str, ...] = (
    "fichier",
    "document",
    "word",
    "docx",
    "pdf",
    "excel",
    "xlsx",
    "tableur",
    "présentation",
    "powerpoint",
    "pptx",
    "csv",
    "rapport",
    "compte rendu",
    "note de synthèse",
    "diaporama",
    "slides",
    "classeur",
)


def messages_have_audio(messages: list) -> bool:
    """Indique si la demande utilisateur contient une entrée audio native."""
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, list) and any(
            isinstance(item, dict) and item.get("type") == "input_audio"
            for item in content
        ):
            return True
    return False


def extract_user_request_text(messages: list) -> str:
    """Extrait uniquement la demande réelle de l'utilisateur.

    Les prompts système, l'historique et le contenu des documents ne doivent
    pas forcer un outil. Dans Ctrl+9, seule la section QUESTION ACTUELLE est
    utilisée pour décider si la demande exige la création d'un fichier.
    """
    parts = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        texts = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(str(item.get("text", "")))
        for text in texts:
            match = re.search(
                r"QUESTION ACTUELLE\s*:\s*(.*?)(?:\n\nDOCUMENTS DISPONIBLES\s*:|\n\nCONTENU TEXTE\s*:|$)",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            parts.append(match.group(1) if match else text)
    return "\n".join(parts).casefold()


def requires_tool_call(messages: list) -> bool:
    """Force un outil seulement pour une demande textuelle explicite d'artefact."""
    if messages_have_audio(messages):
        return False
    text = extract_user_request_text(messages)
    return any(term in text for term in ACTION_TERMS) and any(
        term in text for term in ARTIFACT_TERMS
    )
