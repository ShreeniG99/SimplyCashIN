from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import owner_from_token
from app.db.session import get_session
from app.services.hitl import resolve_escalation

router = APIRouter()


class EscalationHub:
    """In-process fan-out of escalation events, one channel per owner."""

    def __init__(self) -> None:
        self._conns: dict[WebSocket, str] = {}

    async def connect(self, ws: WebSocket, owner_id: str) -> None:
        await ws.accept()
        self._conns[ws] = owner_id

    def disconnect(self, ws: WebSocket) -> None:
        self._conns.pop(ws, None)

    async def broadcast(self, owner_id: str, payload: dict) -> None:
        for ws, owner in list(self._conns.items()):
            if owner != owner_id:
                continue
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 — a dead socket must not break the loop
                self.disconnect(ws)


hub = EscalationHub()


@router.websocket("/ws/escalations")
async def ws_escalations(ws: WebSocket, session: AsyncSession = Depends(get_session)):
    # Browsers cannot set headers on WebSocket upgrade — token rides a query param.
    try:
        owner_id = owner_from_token(ws.query_params.get("token"))
    except HTTPException:
        await ws.close(code=4401)
        return

    await hub.connect(ws, owner_id)
    try:
        while True:
            msg = await ws.receive_json()
            esc_id = msg.get("escalation_id")
            action = msg.get("action")
            try:
                result = await resolve_escalation(
                    session, esc_id, action, msg.get("text"), owner_id)
            except LookupError:
                await ws.send_json({"type": "error", "escalation_id": esc_id,
                                    "detail": "escalation not found"})
                continue
            except ValueError as exc:
                await ws.send_json({"type": "error", "escalation_id": esc_id,
                                    "detail": str(exc)})
                continue
            await ws.send_json({"type": "resolution", "escalation_id": esc_id,
                                "resolution": result["resolution"]})
            await hub.broadcast(owner_id, {"type": "escalation_resolved",
                                           "escalation_id": esc_id,
                                           "resolution": result["resolution"]})
    except WebSocketDisconnect:
        hub.disconnect(ws)
