from pydantic import BaseModel
import uuid

class FileResponse(BaseModel):
    id: uuid.UUID
    original_name: str
    stored_name: str
    mime_type: str | None
    size: int | None
    status: str
    chunk_count: int

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int

