from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from proxylens_server.bootstrap import AppContainer
from proxylens_server.domain.errors import ServerConflictError
from proxylens_server.use_cases.upload_blob import UploadBlobInput, UploadBlobUseCase

from .dtos import UploadBlobResponseDTO


def create_router(get_container: Callable[[], AppContainer]) -> APIRouter:
    router = APIRouter()

    def get_use_case(
        container: AppContainer = Depends(get_container),
    ) -> UploadBlobUseCase:
        return container.upload_blob_use_case

    @router.put("/blobs/{blob_id}", response_model=UploadBlobResponseDTO)
    async def put_blob(
        blob_id: str,
        request: Request,
        use_case: UploadBlobUseCase = Depends(get_use_case),
    ) -> UploadBlobResponseDTO:
        try:
            output = use_case.execute(
                UploadBlobInput(
                    blob_id=blob_id,
                    data=await request.body(),
                    content_type=request.headers.get("content-type"),
                )
            )
            return UploadBlobResponseDTO.from_output(output)
        except ServerConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
