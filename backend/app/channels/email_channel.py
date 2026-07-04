import asyncio
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from app.channels.base import DispatchResult
from app.config import settings


class EmailChannel:
    """Email via aiosmtplib.

    `send_coro` is the injectable transport seam (tests pass a fake coroutine).
    Channel.send is sync, so the coroutine runs on the current loop-free thread,
    or a helper thread when a loop is already running (async API context).
    """

    def __init__(self, send_coro=None, *, host: str | None = None, port: int | None = None,
                 username: str | None = None, password: str | None = None,
                 from_addr: str | None = None, to_lookup: dict[str, str] | None = None):
        self._send_coro = send_coro or self._smtp_send
        self._host = host or settings.smtp_host
        self._port = port or settings.smtp_port
        self._username = username or settings.smtp_user
        self._password = password or settings.smtp_password
        self._from = from_addr or settings.smtp_from
        self._to = to_lookup or {}

    async def _smtp_send(self, msg: EmailMessage) -> None:
        import aiosmtplib
        await aiosmtplib.send(msg, hostname=self._host, port=self._port,
                              username=self._username or None,
                              password=self._password or None, start_tls=True)

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        to = self._to.get(buyer_id)
        if not to:
            return DispatchResult(ok=False, detail=f"no email on file for {buyer_id}")
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = "Payment reminder"
        msg.set_content(message)
        try:
            self._run(self._send_coro(msg))
        except Exception as exc:  # noqa: BLE001 — SMTP/network errors are retryable
            return DispatchResult(ok=False, detail=f"smtp error: {exc}", transient=True)
        return DispatchResult(ok=True, detail=f"email to {to}")

    @staticmethod
    def _run(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
