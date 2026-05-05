from __future__ import annotations

import re
from dataclasses import dataclass

import fitz
import pytesseract
from fastapi import HTTPException
from PIL import Image

OCR_DPI = 300
PAGE_TEXT_QUALITY_THRESHOLD = 80
IMAGE_OCR_AREA_RATIO_THRESHOLD = 0.12

@dataclass
class PageResult:
    page_number: int
    text: str
    method: str

def extract_pages(document: fitz.Document) -> list[PageResult]:
    """Xử lý từng trang độc lặp, trả list PageResult"""
    return [_extract_single_page(page, i+1) for i, page in enumerate(document)]

def merge_page_results(page_results: list[PageResult]) -> tuple[str, str]:
    """
    Trả về (merged_text, method_summary).
    method_summary: "text" | "ocr" | "mixed"
    """

    parts = []
    methods = set()

    for r in page_results:
        if r.text.strip():
            parts.append(f"\n--- PAGE {r.page_number} ---\n{r.text}")
        methods.add(r.method)
    
    merged = "\n".join(parts)

    if methods == {"text"}:
        summary = "text"
    elif methods == {"ocr"}:
        summary = "ocr"
    elif methods == {"text+ocr"}:
        summary = "text+ocr"
    else:
        summary = "mixed"

    return merged, summary

def _extract_single_page(page: fitz.Page, page_number: int) -> PageResult:
    raw_text = page.get_text("text") or ""
    quality = _measure_text_quality(raw_text)
    should_ocr_images = _should_ocr_images(page)

    if quality >= PAGE_TEXT_QUALITY_THRESHOLD and not should_ocr_images:
        return PageResult(page_number, raw_text, "text")
    
    if quality >= PAGE_TEXT_QUALITY_THRESHOLD and should_ocr_images:
        ocr_text = _ocr_page(page)
        merged = _merge_text_and_ocr(raw_text, ocr_text)
        return PageResult(page_number, merged, "text+ocr")
    
    # text yếu hoặc rỗng
    ocr_text = _ocr_page(page)
    if len(ocr_text.strip()) >= len(raw_text.strip()):
        return PageResult(page_number, ocr_text, "ocr")
    
    return PageResult(page_number, raw_text, "text")

def _measure_text_quality(text: str) -> int:
    """Đếm ký tự có nghĩa (bỏ whitespace + control chars)."""
    return len(re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", "", text))

def _should_ocr_images(page: fitz.Page) -> bool:
    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return False

    image_area = 0.0

    for image in page.get_images(full=True):
        xref = image[0]
        for rect in page.get_image_rects(xref):
            image_area += rect.width * rect.height

    return (image_area / page_area) >= IMAGE_OCR_AREA_RATIO_THRESHOLD

def _ocr_page(page: fitz.Page) -> str:
    pixmap = page.get_pixmap(dpi=OCR_DPI, alpha=False)
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

    best_text = ""
    for config in ("--oem 3 --psm 4", "--oem 3 --psm 6"):
        try:
            text = pytesseract.image_to_string(image, lang="eng+vie", config=config)
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
        except pytesseract.TesseractNotFoundError:
            raise HTTPException(status_code=500, detail="Server chưa cài Tesseract OCR binary.")
        except Exception:
            continue

    return best_text

def _merge_text_and_ocr(text_layer: str, ocr_text: str) -> str:
    """
    Text layer làm gốc (encoding chính xác hơn).
    Append những dòng OCR mà text layer không có -> bắt chữ trong ảnh.
    """

    existing = {line.strip() for line in text_layer.splitlines() if line.strip()}
    extras = [
        line for line in ocr_text.splitlines()
        if line.strip() and line.strip() not in existing
    ]
    
    if extras:
        return text_layer.strip() + "\n" + "\n".join(extras)
    
    return text_layer
