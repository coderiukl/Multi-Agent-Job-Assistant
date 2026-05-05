from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from services.cv.cv_service import process_cv_pdf

router = APIRouter(prefix="/cv", tags=["CV"])

def build_cv_embedding_documents(result):
    details = result.details
    documents = []

    if details.get("summary"):
        documents.append({
            "field": "summary",
            "text": details['summary'],
        })
    
    if details.get("skills"):
        skill_text_parts = []

        for group_name, skills in details['skills'].items():
            skill_text_parts.append(f"{group_name}: {', '.join(skills)}")
        
        skill_text = "\n".join(skill_text_parts)

        if skill_text.strip():
            documents.append({
                "field": "skills",
                "text": skill_text,
            })

    for index, exp in enumerate(details.get("work_experience", [])):
        text = "\n".join([
            exp.get("title") or "",
            exp.get("company") or "",
            exp.get("date") or "",
            "\n".join(exp.get("responsibilities", [])),
        ]).strip()

        if text:
            documents.append({
                "field": "work_experience",
                "index": index,
                "text": text,
            })
    
    for index, project in enumerate(details.get("projects", [])):
        text = "\n".join([
            project.get("title") or "",
            project.get("date") or "",
            ", ".join(project.get("tools", [])),
            "\n".join(project.get("descriptions", [])),
        ]).strip()

        if text:
            documents.append({
                "field": "projects",
                "index": index,
                "text": text,
            })
    
    for index, edu in enumerate(details.get("education", [])):
        text = "\n".join([
            edu.get("school") or "",
            edu.get("degree") or "",
            edu.get("major") or "",
            edu.get("date") or "",
            "\n".join(edu.get("descriptions", []))
        ]).strip()

        if text:
            documents.append({
                "field": "education",
                "index": index,
                "text": text,
            })
    
    return documents

@router.post("/upload")
async def upload_cv(request: Request, file: UploadFile = File(...)):
    try:
        result = await process_cv_pdf(file)

        documents = build_cv_embedding_documents(result)
        texts = [document['text'] for document in documents]

        if not texts:
            return {
                "success": True,
                "message": "Upload và xử lý CV thành công, nhưng không có nội dung đủ rõ để tạo embedding.",
                "data": {
                    "filename": result.filename,
                    "page_count": result.page_count,
                    "extraction_method": result.extraction_method,
                    "embedding_count": 0,
                    "point_ids": [],
                    "details": result.details,
                }
            }

        try:
            vectors = request.app.state.embedding_service.embed_texts(texts)
        except Exception as e:
            print("Embedding error:", repr(e))
            raise HTTPException(status_code=503, detail="Không tạo được embedding cho CV.")

        payloads = [
            {
                "type": "cv",
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
                vectors=vectors,
                payloads=payloads
            )
        except Exception as e:
            print("Qdrant error:", repr(e))
            raise HTTPException(status_code=503, detail="Không lưu được embedding vào Qdrant.")

        return {
            "success": True,
            "message": "Upload và xử lý CV thành công.",
            "data": {
                "filename": result.filename,
                "page_count": result.page_count,
                "extraction_method": result.extraction_method,
                "embedding_count": len(point_ids),
                "point_ids": point_ids,
                "details": result.details,
            }
        }
    except HTTPException:
        raise

    except Exception as e:
        print("Upload CV error:", e)
        raise HTTPException(status_code=500, detail="Có lỗi xảy ra khi xử lý CV.")
