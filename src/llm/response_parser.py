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
    """Supprime les balises spéciales et métadonnées de fin de tour des flux SSE."""
    if not text:
        return ""
    for token in CLEAN_TOKENS:
        text = text.replace(token, "")
    return text


def split_thinking_and_answer(raw_text: str) -> Tuple[str, str]:
    """Sépare les réflexions de raisonnement (<think>...</think>) de la réponse finale."""
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
    thinking = "\n".join(part.strip() for part in thinking_parts if part.strip())
    return thinking.strip(), answer.strip()


def parse_audio_response(raw_text: str) -> Tuple[str, str]:
    """Extrait le transcript pour le titre et masque les balises dans la réponse."""
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
