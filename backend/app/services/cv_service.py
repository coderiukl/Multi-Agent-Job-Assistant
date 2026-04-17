import uuid
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import File as FileModel, FileChunk, User
from app.parsers.cv_parser import CVParser, chunk_text
from app.parsers.text_cleaner import clean_text
from app.parsers.utils import ParseError
from app.services.embedding_service import embed_file

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads/cvs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}


async def upload_and_embed_cv(
    file: UploadFile,
    db: AsyncSession,
    current_user: User,
) -> tuple[FileModel, int]:
    """
    Dùng chung cho cả cv.py và conversation.py.
    Trả về (db_file, chunk_count).
    """

    # 1. Validate extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Chỉ chấp nhận .pdf hoặc .docx. Nhận được: '{ext}'",
        )

    # 2. Validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Tối đa {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # 3. Lưu disk
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(file_bytes)

    # 4. Tạo DB record
    db_file = FileModel(
        user_id=current_user.id,
        original_name=original_name,
        stored_name=stored_name,
        file_path=str(file_path),
        mime_type=file.content_type,
        size=len(file_bytes),
        status="parsing",
    )
    db.add(db_file)
    await db.flush()

    # 5. Parse + chunk + embed
    try:
        parser = CVParser()
        raw_text = clean_text(parser.parse(str(file_path)))
        chunks_data = chunk_text(raw_text, chunk_size=300, overlap=50)

        for chunk in chunks_data:
            db.add(FileChunk(
                file_id=db_file.id,
                chunk_index=chunk["chunk_index"],
                content=clean_text(chunk["content"]),
                metadata_json={"token_count": chunk.get("token_count", 0)},
            ))

        db_file.status = "embedded"
        await embed_file(file_id=db_file.id, db=db)
        await db.commit()
        await db.refresh(db_file)
        
        return db_file, len(chunks_data)

    except ParseError as exc:
        db_file.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        db_file.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "UNEXPECTED_ERROR", "message": str(exc)},
        )

    