from __future__ import annotations

import yaml
from fastapi import APIRouter, FastAPI, Response
from scalar_fastapi import get_scalar_api_reference


def create_router(app: FastAPI) -> APIRouter:
    router = APIRouter()

    @router.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml() -> Response:
        return Response(
            yaml.safe_dump(app.openapi(), sort_keys=False),
            media_type="application/yaml",
        )

    @router.get("/scalar", include_in_schema=False)
    def scalar() -> Response:
        return get_scalar_api_reference(
            openapi_url="/openapi.json", title="ProxyLens Server"
        )

    return router
