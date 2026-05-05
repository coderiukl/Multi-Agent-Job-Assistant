from __future__ import annotations

import re
from dataclasses import dataclass, field

import fitz
from fastapi import HTTPException, UploadFile

from services.cv.pdf_extractor import PageResult, extract_pages, merge_page_results
from services.llm_extractor import extract_with_llm, normalize_llm_output

from services.cv.regex_parser import (
    normalize_cv_text,
    extract_cv_details_regex,
    _extract_email,
    _extract_phone
)

MAX_FILE_SIZE = 20 * 1024 *  1024
MAX_PAGES = 10
USE_LLM = True

@dataclass
class CvPdfResult:
    filename: str
    page_count: int
    text: str
    extraction_method: str
    email: str | None
    phone: str | None
    details: dict
    page_results: list[PageResult] = field(default_factory=list)

async def process_cv_pdf(file: UploadFile) -> CvPdfResult:
    file_bytes = await file.read()

    _validate_upload(file, file_bytes)

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail='File PDF bị lỗi hoặc không thể mở.')
    
    try:
        _validate_document(document)

        page_results = extract_pages(document)
        raw_text, method = merge_page_results(page_results)
        normalized_text = normalize_cv_text(raw_text)

        if not normalized_text:
            raise HTTPException(status_code=422, detail="Không đọc được nội dung CV. Vui lòng upload PDF có text rõ hoặc bản scan chất lượng tốt.")

        details = _extract_details(normalized_text)

        return CvPdfResult(
            filename=file.filename or "cv.pdf",
            page_count=document.page_count,
            text=normalized_text,
            extraction_method=method,
            email=details.get('email'),
            phone=details.get('phone'),
            details=details,
            page_results=page_results,
        )
    finally:
        document.close()

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

def _extract_details(text: str) -> dict:
    """LLM → fallback regex."""
    if USE_LLM:
        raw = extract_with_llm(text)

        # Ép Ollama unload model ngay để giải phóng VRAM cho bge-m3
        _unload_ollama_model()

        if raw:
            details = _normalize_cv_details(normalize_llm_output(raw))
            # Regex backup cho email/phone nếu LLM miss
            if not details["email"]:
                details["email"] = _extract_email(text)
            if not details["phone"]:
                details["phone"] = _extract_phone(text)
            return details

    print("[CV] Falling back to regex extraction")
    return _normalize_cv_details(extract_cv_details_regex(text))

def _unload_ollama_model() -> None:
    """
    Gọi Ollama API với keep_alive=0 để unload model khỏi VRAM ngay lập tức.
    Ollama mặc định giữ model 5 phút — cần unload thủ công để dư VRAM cho bge-m3.
    """
    try:
        import requests
        from ..llm_extractor import OLLAMA_BASE_URL, OLLAMA_MODEL
        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "keep_alive": 0 # 0 = unload ngay lập tức
            },
            timeout=10
        )
        print("[LLM] Model unloaded from VRAM")
    except Exception as e:
        print(f"[LLM] Unload warning: {e}")

def _validate_upload(file: UploadFile, file_bytes: bytes) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF.")
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Content-Type không hợp lệ.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File PDF rỗng.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File PDF quá lớn. Giới hạn là 20MB.")
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File upload không phải PDF hợp lệ.")
    
def _validate_document(document: fitz.Document) -> None:
    if document.is_encrypted:
        raise HTTPException(status_code=400, detail="PDF đang bị khóa mật khẩu.")
    if document.page_count == 0:
        raise HTTPException(status_code=400, detail="PDF không có trang nào.")
    if document.page_count > MAX_PAGES:
        raise HTTPException(status_code=413, detail=f"CV quá dài. Giới hạn tối đa {MAX_PAGES} trang.")
    
def _normalize_cv_details(details: dict) -> dict:
    return {
        "full_name": details.get("full_name"),
        "email": details.get("email"),
        "phone": details.get("phone"),
        "location": details.get("location"),
        "summary": details.get("summary") or "",
        "skills": details.get("skills") or {},
        "work_experience": details.get("work_experience") or [],
        "projects": details.get("projects") or [],
        "education": details.get("education") or [],
    }
