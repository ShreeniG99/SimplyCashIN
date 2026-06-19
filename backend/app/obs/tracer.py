from typing import Any, Protocol

from app.config import settings


class Tracer(Protocol):
    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None: ...


class NullTracer:
    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        return None


class RecordingTracer:
    """In-memory tracer for tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        self.events.append({"agent": agent, "model": model, "prompt": prompt,
                            "response": response, "meta": meta})


class PostHogTracer:
    """Sends agent calls/decisions to PostHog LLM analytics. Never raises."""

    def __init__(self, api_key: str | None = None, host: str | None = None):
        import posthog
        self._client = posthog.Posthog(api_key or settings.posthog_api_key,
                                       host=host or settings.posthog_host)

    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        try:
            self._client.capture(
                distinct_id=meta.get("owner_id", "system"),
                event="$ai_generation",
                properties={"$ai_model": model, "$ai_input": prompt,
                            "$ai_output_choices": response, "scin_agent": agent, **meta},
            )
        except Exception:  # noqa: BLE001 — observability must never break a cycle
            pass


def default_tracer() -> Tracer:
    return PostHogTracer() if settings.posthog_api_key else NullTracer()
