"""Contrats typés pour les messages compatibles OpenAI/llama.cpp."""

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union


class LlmContentPart(TypedDict, total=False):
    type: str
    text: str
    image_url: Dict[str, str]


class LlmMessage(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[LlmContentPart]]
    name: str
    tool_call_id: str
    tool_calls: List[Dict[str, Any]]


class LlmChoice(TypedDict, total=False):
    index: int
    message: LlmMessage
    text: str
    delta: Dict[str, Any]
    finish_reason: Optional[str]


class LlmResponse(TypedDict, total=False):
    choices: List[LlmChoice]
    content: Union[str, List[Dict[str, Any]]]


class DocumentTurn(TypedDict, total=False):
    role: Literal["user", "assistant", "tool"]
    content: str
    thinking: str
    sources: List[Dict[str, Any]]
