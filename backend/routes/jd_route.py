from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Form
from pydantic import BaseModel, Field

from qdrant_client.models import FieldCondition, Filter, MatchValue
from services.jd.jd_service import (
    JDResult,
    build_jd_embedding_documents,
    build_jd_embedding_text,
    process_jd_text
)

router = APIRouter(prefix='/jd', tags=['JD'])

class JDUploadRequest(BaseModel):
    text: str = Field(min_length=20)
    source: str = "manual"

class JDMatchRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0)

def _build_filter(filters: dict) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key=key,
                match=MatchValue(value=value)
            )
            for key, value in filters.items()
        ]
    )

def _jd_payload(jd: JDResult, jd_id: str, source: str, embedding_text: str) -> dict:
    return {
        "type": "jd",
        "jd_id": jd_id,
        "title": jd.title,
        "department": jd.department,
        "location": jd.location,
        "job_type": jd.job_type,
        "seniority": jd.seniority,
        "required_skills": jd.required_skills,
        "preferred_skills": jd.preferred_skills,
        "salary_min": jd.salary_min,
        "salary_max": jd.salary_max,
        "salary_currency": jd.salary_currency,
        "source": source,
        "extraction_method": jd.extraction_method,
        "embedding_text": embedding_text[:4000],
        "raw_text": jd.raw_text[:4000],
    }

def _format_jd_point(point) -> dict:
    payload = point.payload or {}

    return {
        "point_id": str(point.id),
        "jd_id": payload.get("jd_id"),
        "title": payload.get("title"),
        "department": payload.get("department"),
        "location": payload.get("location"),
        "job_type": payload.get("job_type"),
        "seniority": payload.get("seniority"),
        "required_skills": payload.get("required_skills") or [],
        "preferred_skills": payload.get("preferred_skills") or [],
        "salary_min": payload.get("salary_min"),
        "salary_max": payload.get("salary_max"),
        "salary_currency": payload.get("salary_currency"),
        "source": payload.get("source"),
        "extraction_method": payload.get("extraction_method"),
    }

@router.post("/upload")
async def upload_jd(request: Request, text: str = Form(..., min_length=20), source: str = Form("manual")):
    jd_id = str(uuid4())
    body = JDUploadRequest(text=text, source=source)
    
    try:
        jd = process_jd_text(body.text)
    except HTTPException:
        raise
    except Exception as e:
        print("[JD] Parse error:", repr(e))
        raise HTTPException(status_code=500, detail="Lỗi khi phân tích JD.")

    documents = build_jd_embedding_documents(jd)
    texts = [document['text'] for document in documents]

    if not texts:
        raise HTTPException(status_code=422, detail="JD không có nội dung đủ rõ để tạo embedding.")
    
    try:
        dense_vectors = request.app.state.embedding_service.embed_texts(texts)

        sparse_service = getattr(request.app.state, "sparse_embedding_service", None)
        sparse_vectors = sparse_service.embed_texts(texts) if sparse_service else None
    except Exception as e:
        print("[JD] Embedding error:", repr(e))
        raise HTTPException(status_code=503, detail="Không tạo được embedding cho JD.")
    
    payloads = [
        {
            **_jd_payload(
                jd=jd,
                jd_id=jd_id,
                source=body.source,
                embedding_text=build_jd_embedding_text(jd),
            ),
            "field": document['field'],
            "field_index": index,
            "text": document["text"],
        }
        for index, document in enumerate(documents)
    ]

    try:
        point_ids = request.app.state.qdrant_service.upsert(
            vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
            payloads=payloads
        )
    except Exception as e:
        print("[JD] Qdrant upsert error:", repr(e))
        raise HTTPException(status_code=503, detail="Không lưu được JD vào Qdrant.")
    
    return {
        "success": True,
        "message": "Upload JD thanh cong.",
        "data": {
            "jd_id": jd_id,
            "title": jd.title,
            "extraction_method": jd.extraction_method,
            "embedding_count": len(point_ids),
            "point_ids": point_ids,
            "has_sparse": sparse_vectors is not None,
            "parsed": {
                "department": jd.department,
                "location": jd.location,
                "job_type": jd.job_type,
                "seniority": jd.seniority,
                "required_skills": jd.required_skills,
                "preferred_skills": jd.preferred_skills,
                "requirements_count": len(jd.requirements),
                "responsibilities_count": len(jd.responsibilities),
                "salary_min": jd.salary_min,
                "salary_max": jd.salary_max,
                "salary_currency": jd.salary_currency,
            },
        },
    }

@router.get('/list')
async def list_jds(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    qdrant = request.app.state.qdrant_service

    try:
        points, _ = qdrant.client.scroll(
            collection_name=qdrant.collection_name,
            scroll_filter=_build_filter({"type": "jd"}),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as e:
        print("[JD] List error:", repr(e))
        raise HTTPException(status_code=503, detail="Không lấy được danh sách JD.")
    
    # Mỗi JD có nhiều chunks, nên group theo jd_id để list không bị trùng
    jd_map = {}

    for point in points:
        payload = point.payload or {}
        jd_id = payload.get('jd_id')

        if not jd_id:
            continue

        if jd_id not in jd_map:
            jd_map[jd_id] = _format_jd_point(point)
            jd_map[jd_id]['chunk_count'] = 0
        
        jd_map[jd_id]['chunk_count'] += 1

    return {
        "success": True,
        "count": len(jd_map),
        "data": list(jd_map.values())
    }

@router.delete('/{jd_id}')
async def delete_jd(jd_id: str, request: Request):
    try:
        request.app.state.qdrant_service.delete_by_filter({"jd_id": jd_id})
    except Exception as e:
        print("[JD] Delete error:", repr(e))
        raise HTTPException(status_code=503, detail="Không xóa được JD.")
    
    return {
        "success": True,
        "message": f"Đã xóa JD {jd_id}.",
    }

@router.post("/{jd_id}/match")
async def match_jd(jd_id: str, body: JDMatchRequest, request: Request):
    qdrant = request.app.state.qdrant_service

    try:
        jd_points, _ = qdrant.client.scroll(
            collection_name=qdrant.collection_name,
            scroll_filter=_build_filter({
                "type": "jd",
                "jd_id": jd_id,
            }),
            limit=20,
            with_payload=True,
            with_vectors=False
        )
    except Exception as e:
        print("[JD Match] Find JD error:",repr(e))
        raise HTTPException(status_code=503, detail="Lỗi khi tìm JD.")
    
    if not jd_points:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy JD id={jd_id}")
    
    jd_payload = jd_points[0].payload or {}

    # Dùng toàn bộ chunks của JD làm query text sẽ tốt hơn chỉ dùng 1 raw_text ngắn.
    query_text = "\n\n".join(
        (point.payload or {}).get("text") or ""
        for point in jd_points
    ).strip()

    if not query_text:
        query_text = jd_payload.get("embedding_text") or jd_payload.get("raw_text") or ""

    if not query_text.strip():
        raise HTTPException(status_code=422, detail="JD không có text để match.")
    
    try:
        dense_query = request.app.state.embedding_service.embed_text(query_text)

        sparse_service = getattr(request.app.state, "sparse_embedding_service", None)
        sparse_query = sparse_service.embed_text(query_text) if sparse_service else None
    except Exception as e:
        print("[JD Match] Query embedding error:", repr(e))
        raise HTTPException(status_code=503, detail="Không tạo được query embedding.")

    # Quan trọng: chỉ tìm CV đã nộp vào đúng JD này.
    cv_filter = {
        "type": "cv",
        "jd_id": jd_id,
    }

    try:
        if sparse_query:
            raw_results = qdrant.hybrid_search(
                query_dense=dense_query,
                query_sparse=sparse_query,
                limit=body.limit * 5,
                filters=cv_filter,
            )
            search_mode = "hybrid"
        else:
            raw_results = qdrant.search(
                query_vector=dense_query,
                limit=body.limit * 5,
                filters=cv_filter,
            )
            search_mode = "dense"
    except Exception as e:
        print("[JD Match] Search error:", repr(e))
        raise HTTPException(status_code=503, detail="Loi khi search CV.")
    
    if body.min_score > 0:
        raw_results = [
            point for point in raw_results
            if float(getattr(point, "score", 0.0)) >= body.min_score
        ]

    candidate_map = {}

    for point in raw_results:
        payload = point.payload or {}
        score = round(float(point.score), 4)
        candidate_key = (
            payload.get("cv_id")
            or payload.get("email")
            or payload.get("filename")
            or str(point.id)
        )

        if candidate_key not in candidate_map:
            candidate_map[candidate_key] = {
                "score": score,
                "cv_id": payload.get("cv_id"),
                "full_name": payload.get("full_name"),
                "email": payload.get("email"),
                "phone": payload.get("phone"),
                "filename": payload.get("filename"),
                "best_field": payload.get("field"),
                "text_preview": (payload.get("text") or "")[:200],
                "matched_chunks": [],
            }

        candidate_map[candidate_key]["matched_chunks"].append({
            "point_id": str(point.id),
            "field": payload.get("field"),
            "score": score,
            "text_preview": (payload.get("text") or "")[:120],
        })

        if score > candidate_map[candidate_key]["score"]:
            candidate_map[candidate_key]["score"] = score
            candidate_map[candidate_key]["best_field"] = payload.get("field")
            candidate_map[candidate_key]["text_preview"] = (payload.get("text") or "")[:200]

    candidates = sorted(
        candidate_map.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    for candidate in candidates:
        candidate["matched_chunks"] = sorted(
            candidate["matched_chunks"],
            key=lambda item: item["score"],
            reverse=True,
        )[:5]

    return {
        "success": True,
        "jd_id": jd_id,
        "jd_title": jd_payload.get("title"),
        "search_mode": search_mode,
        "total": min(len(candidates), body.limit),
        "results": candidates[: body.limit],
    }
