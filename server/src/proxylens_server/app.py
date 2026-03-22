from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI

from proxylens_server.bootstrap import AppContainer, create_container
from proxylens_server.config import ServerConfig
from proxylens_server.infra.routes.blobs.router import (
    create_router as create_blob_router,
)
from proxylens_server.infra.routes.docs.router import (
    create_router as create_docs_router,
)
from proxylens_server.infra.routes.events.router import (
    create_router as create_event_router,
)
from proxylens_server.infra.routes.requests.router import (
    create_router as create_request_router,
)


def _default_data_dir() -> Path:
    return Path(
        os.environ.get("PROXYLENS_SERVER_DATA_DIR", ".proxylens-server-data")
    ).resolve()


def create_app(config: ServerConfig | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = create_container(
            config or ServerConfig(data_dir=_default_data_dir())
        )
        try:
            yield
        finally:
            app.state.container.close()

    app = FastAPI(
        title="ProxyLens Server",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    def get_container() -> AppContainer:
        return app.state.container

    app.include_router(create_blob_router(get_container))
    app.include_router(create_event_router(get_container))
    app.include_router(create_request_router(get_container))
    app.include_router(create_docs_router(app))
    return app
