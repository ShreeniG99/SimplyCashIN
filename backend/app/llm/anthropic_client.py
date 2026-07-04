from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.llm.base import LLMError, LLMRefusal

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            resp = self._client.messages.create(
                model=self._model, max_tokens=max_tokens,
                thinking={"type": "adaptive"}, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as exc:
            raise LLMError(f"anthropic call failed: {exc}") from exc
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    def complete_structured(self, system: str, user: str, schema: type[T],
                            max_tokens: int = 1024) -> T:
        try:
            resp = self._client.messages.parse(
                model=self._model, max_tokens=max_tokens,
                thinking={"type": "adaptive"}, system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except (anthropic.AnthropicError, ValidationError) as exc:
            raise LLMError(f"anthropic structured call failed: {exc}") from exc
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        if resp.parsed_output is None:
            raise LLMError("no structured output parsed")
        return resp.parsed_output
