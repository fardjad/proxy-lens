from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.use_cases.upload_blob import UploadBlobOutput


class UploadBlobResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_id: str
    status: str

    @classmethod
    def from_output(cls, output: UploadBlobOutput) -> "UploadBlobResponseDTO":
        return cls(blob_id=output.blob_id, status=output.status)
