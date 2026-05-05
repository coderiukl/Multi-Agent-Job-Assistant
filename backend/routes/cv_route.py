from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from qdrant_client.models import FieldCondition, Filter, MatchValue

from services.cv.cv_service import process_cv_pdf, build_cv_embedding_documents

from uuid import uuid4 

router = APIRouter(prefix="/cv", tags=["CV"])

def _build_filter(filters: dict) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key=key,
                match=MatchValue(value=value),
            )
            for key, value in filters.items()
        ]
    )

def _ensure_jd_exists(request: Request, jd_id: str) -> None:
    qdrant = request.app.state.qdrant_service

    try:
        points, _ = qdrant.client.scroll(
            collection_name=qdrant.collection_name,
            scroll_filter=_build_filter({
                "type": "jd",
                "jd_id": jd_id
            }),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as e:
        print("Check JD error:", repr(e))
        raise HTTPException(status_code=503, detail='Không kiểm tra được JD.')
    
    if not points:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy JD id={jd_id}")

@router.post("/upload")
async def upload_cv(request: Request, file: UploadFile = File(...), jd_id: str | None = None):
    if not jd_id:
        raise HTTPException(status_code=400, detail="Thiếu jd_id khi upload CV.")
    
    _ensure_jd_exists(request, jd_id)

    cv_id = str(uuid4())
    try:
        result = await process_cv_pdf(file)

        documents = build_cv_embedding_documents(result)
        texts = [document['text'] for document in documents]

        if not texts:
            return {
                "success": True,
                "message": "Upload CV thành công, nhưng không có nội dung đủ rõ để tạo embedding.",
                "data": {
                    "jd_id": jd_id,
                    "cv_id": cv_id,
                    "filename": result.filename,
                    "page_count": result.page_count,
                    "extraction_method": result.extraction_method,
                    "embedding_count": 0,
                    "point_ids": [],
                    "details": result.details,
                }
            }

        try:
            dense_vectors = request.app.state.embedding_service.embed_texts(texts)

            sparse_service = getattr(request.app.state, "sparse_embedding_service", None)
            sparse_vectors = sparse_service.embed_texts(texts) if sparse_service else None
        except Exception as e:
            print("Embedding error:", repr(e))
            raise HTTPException(status_code=503, detail="Không tạo được embedding cho CV.")

        payloads = [
            {
                "type": "cv",
                "jd_id": jd_id,
                "cv_id": cv_id,
                "filename": result.filename,
                "page_count": result.page_count,
                "extraction_method": result.extraction_method,
                "full_name": result.details.get('full_name'),
                "email": result.email,
                "phone": result.phone,
                "location": result.details.get('location'),
                "field": document['field'],
                "field_index": document.get('index'),
                "text": document['text'],
            }
            for document in documents
        ]

        try:
            point_ids = request.app.state.qdrant_service.upsert(
                vectors=dense_vectors,
                sparse_vectors=sparse_vectors,
                payloads=payloads
            )
        except Exception as e:
            print("Qdrant error:", repr(e))
            raise HTTPException(status_code=503, detail="Không lưu được CV vào Qdrant.")

        return {
            "success": True,
            "message": "Upload CV thành công.",
            "data": {
                "jd_id": jd_id,
                "cv_id": cv_id,
                "filename": result.filename,
                "page_count": result.page_count,
                "extraction_method": result.extraction_method,
                "embedding_count": len(point_ids),
                "point_ids": point_ids,
                "has_sparse": sparse_vectors is not None,
                "details": result.details,
            }
        }
    except HTTPException:
        raise

    except Exception as e:
        print("Upload CV error:", e)
        raise HTTPException(status_code=500, detail="Có lỗi xảy ra khi xử lý CV.")
