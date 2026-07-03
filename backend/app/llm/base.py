from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Agent could not produce usable output."""


class LLMRefusal(LLMError):
    """The model declined the request (stop_reason == 'refusal')."""


class LLM(Protocol):
    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str: ...

    def complete_structured(self, system: str, user: str, schema: type[T],
                            max_tokens: int = 1024) -> T: ...
