"""Contrats typés pour les messages compatibles OpenAI/llama.cpp."""

from typing import Any, Literal, TypedDict


class LlmContentPart(TypedDict, total=False):
    type: str
    text: str
    image_url: dict[str, str]


class LlmMessage(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[LlmContentPart]
    name: str
    tool_call_id: str
    tool_calls: list[dict[str, Any]]


class LlmChoice(TypedDict, total=False):
    index: int
    message: LlmMessage
    text: str
    delta: dict[str, Any]
    finish_reason: str | None


class LlmResponse(TypedDict, total=False):
    choices: list[LlmChoice]
    content: str | list[dict[str, Any]]


class DocumentTurn(TypedDict, total=False):
    role: Literal["user", "assistant", "tool"]
    content: str
    thinking: str
    sources: list[dict[str, Any]]
