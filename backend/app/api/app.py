from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    scheduler = None
    if settings.enable_scheduler:
        from app.db.session import SessionFactory
        from app.scheduler.daily import build_scheduler
        scheduler = build_scheduler(SessionFactory)
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="SimplyCashIN", version="0.1.0", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
