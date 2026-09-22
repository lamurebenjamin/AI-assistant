# -*- coding: utf-8 -*-
"""Parseurs et nettoyeurs de réponses générées par le LLM."""

import re
from typing import Tuple

CLEAN_TOKENS = (
    "<|end|>",
    "<end_of_turn>",
    "<|channel|>final",
    "<channel>final",
    "<|channel|>answer",
    "<channel>answer",
)


def clean_chunk(text: str) -> str:
    """Nettoie un fragment SSE ; accepte une chaîne vide et ne lève pas d'erreur."""
    if not text:
        return ""
    for token in CLEAN_TOKENS:
        text = text.replace(token, "")
    return text


def clean_thinking_text(text: str) -> str:
    """Supprime les en-têtes de raisonnement ajoutés par certains modèles."""
    if not text:
        return ""
    return re.sub(r"(?im)^\s*thinking\s+process\s*:\s*", "", text)


def split_thinking_and_answer(raw_text: str) -> Tuple[str, str]:
    """Retourne ``(raisonnement, réponse)`` après extraction des balises ``think``."""
    normalized = re.sub(r"</think>\s*<think>", "", raw_text, flags=re.IGNORECASE)
    thinking_parts = []

    def extract_complete(match):
        thinking_parts.append(match.group(1))
        return ""

    answer = re.sub(
        r"<think>(.*?)</think>", extract_complete, normalized, flags=re.IGNORECASE | re.DOTALL
    )
    open_match = re.search(r"<think>(.*)$", answer, flags=re.IGNORECASE | re.DOTALL)
    if open_match:
        thinking_parts.append(open_match.group(1))
        answer = answer[: open_match.start()]
    answer = re.sub(r"</?think>", "", answer, flags=re.IGNORECASE)
    thinking = clean_thinking_text(
        "\n".join(part.strip() for part in thinking_parts if part.strip())
    )
    return thinking.strip(), answer.strip()


def parse_audio_response(raw_text: str) -> Tuple[str, str]:
    """Retourne ``(transcription, réponse)`` en tolérant les balises incomplètes."""
    transcript = ""
    transcript_match = re.search(
        r"<transcript>(.*?)</transcript>", raw_text, re.IGNORECASE | re.DOTALL
    )
    if transcript_match:
        transcript = re.sub(r"\s+", " ", transcript_match.group(1)).strip()

    answer_match = re.search(
        r"<answer>(.*?)(?:</answer>|$)", raw_text, re.IGNORECASE | re.DOTALL
    )
    if answer_match:
        answer = answer_match.group(1).strip()
    elif transcript_match:
        answer = raw_text[transcript_match.end() :]
        answer = re.sub(r"^\s*<answer>", "", answer, flags=re.IGNORECASE).strip()
    else:
        # Tant que la transcription n'est pas terminée, rien n'est affiché dans le corps
        answer = "" if re.search(r"<transcript>", raw_text, re.IGNORECASE) else raw_text
    return transcript, answer
