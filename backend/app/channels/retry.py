import time

from app.channels.base import Channel, DispatchResult


class RetryingChannel:
    """Retries transient send failures with exponential backoff (max `retries`
    attempts). Permanent failures and exhaustion pass through as ok=False, which
    the Orchestrator already turns into an escalation."""

    def __init__(self, inner: Channel, *, retries: int = 3, backoff_base: float = 0.5,
                 sleep=time.sleep):
        self._inner = inner
        self._retries = retries
        self._backoff_base = backoff_base
        self._sleep = sleep

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        result = DispatchResult(ok=False, detail="not attempted")
        for attempt in range(self._retries):
            result = self._inner.send(
                buyer_id=buyer_id, message=message, channel_kind=channel_kind)
            if result.ok or not result.transient:
                return result
            if attempt < self._retries - 1:
                self._sleep(self._backoff_base * (2 ** attempt))
        return result
