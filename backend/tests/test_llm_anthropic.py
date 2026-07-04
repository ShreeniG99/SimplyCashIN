"""AnthropicClient must surface SDK failures as typed LLMError so the
Orchestrator's escalate-on-LLM-failure path works with the real client
(spec: "LLM failures (rate limit, 5xx) surface as a typed LLMError")."""
import anthropic
import httpx
import pytest
from pydantic import BaseModel

from app.llm.anthropic_client import AnthropicClient
from app.llm.base import LLMError


class _Plan(BaseModel):
    upfront_pct: int


def _client_with_failing_messages(exc: Exception) -> AnthropicClient:
    client = AnthropicClient(api_key="test-key")

    class _FailingMessages:
        def create(self, **kw):
            raise exc

        def parse(self, **kw):
            raise exc

    client._client.messages = _FailingMessages()
    return client


_API_ERROR = anthropic.APIConnectionError(
    request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_complete_text_wraps_sdk_error_as_llmerror():
    client = _client_with_failing_messages(_API_ERROR)
    with pytest.raises(LLMError):
        client.complete_text("sys", "user")


def test_complete_structured_wraps_sdk_error_as_llmerror():
    client = _client_with_failing_messages(_API_ERROR)
    with pytest.raises(LLMError):
        client.complete_structured("sys", "user", _Plan)


def test_complete_structured_wraps_validation_error_as_llmerror():
    from pydantic import ValidationError

    try:
        _Plan(upfront_pct="not-a-number")
    except ValidationError as exc:
        validation_error = exc
    client = _client_with_failing_messages(validation_error)
    with pytest.raises(LLMError):
        client.complete_structured("sys", "user", _Plan)
