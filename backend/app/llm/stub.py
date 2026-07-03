from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)


class StubLLM:
    """Deterministic LLM for tests and no-key runtime."""

    def __init__(self, text_response: str = "Namaste, a gentle reminder about your invoice.",
                 structured_response: BaseModel | None = None,
                 raise_error: bool = False):
        self.text_response = text_response
        self.structured_response = structured_response
        self.raise_error = raise_error
        self.calls: list[tuple] = []

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        self.calls.append(("text", system, user))
        if self.raise_error:
            raise LLMError("stub forced error")
        return self.text_response

    def complete_structured(self, system: str, user: str, schema, max_tokens: int = 1024):
        self.calls.append(("structured", system, user))
        if self.raise_error or self.structured_response is None:
            raise LLMError("stub forced error / no structured response set")
        return self.structured_response
