from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMError, LLMRefusal

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.messages.create(
            model=self._model, max_tokens=max_tokens,
            thinking={"type": "adaptive"}, system=system,
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    def complete_structured(self, system: str, user: str, schema: type[T],
                            max_tokens: int = 1024) -> T:
        resp = self._client.messages.parse(
            model=self._model, max_tokens=max_tokens,
            thinking={"type": "adaptive"}, system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        if resp.parsed_output is None:
            raise LLMError("no structured output parsed")
        return resp.parsed_output
