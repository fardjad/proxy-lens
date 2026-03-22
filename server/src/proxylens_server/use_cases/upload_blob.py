from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.infra.persistence.repositories.blobs import BlobRepository


class UploadBlobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_id: str
    data: bytes
    content_type: str | None = None


class UploadBlobOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_id: str
    status: str


class UploadBlobUseCase:
    def __init__(self, blob_repository: BlobRepository) -> None:
        self._blob_repository = blob_repository

    def execute(self, data: UploadBlobInput) -> UploadBlobOutput:
        result = self._blob_repository.save_uploaded_blob(
            blob_id=data.blob_id,
            data=data.data,
            content_type=data.content_type,
        )
        return UploadBlobOutput(blob_id=result.blob_id, status=result.status)
