from __future__ import annotations

import logging
from pathlib import Path

from app.parsers.utils import ParseError, detect_file_type
from app.parsers.pdf_parser import PDFParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.ocr_parser import OCRParser

logger = logging.getLogger(__name__)

# Ngưỡng ký tự tối thiểu: nếu PDFParser trả về ít hơn thế → coi là scan, fallback OCR
_OCR_FALLBACK_THRESHOLD = 30


class CVParser:
    """
    Orchestrator chọn đúng parser dựa trên extension của file.

    Strategy cho PDF:
        1. Thử PDFParser (pypdf) trước — nhanh, chính xác với PDF có text.
        2. Nếu text quá ngắn (< _OCR_FALLBACK_THRESHOLD ký tự) → PDF scan,
           fallback sang OCRParser (PyMuPDF + pytesseract).

    Strategy cho DOCX:
        DOCXParser trực tiếp, không cần fallback.

    Raises:
        ParseError — tất cả lỗi đều được wrap về ParseError với code cụ thể.
    """

    def __init__(self, ocr_language: str = "eng+vie"):
        self._pdf_parser = PDFParser()
        self._docx_parser = DOCXParser()
        self._ocr_parser = OCRParser(language=ocr_language)

    def parse(self, file_path: str) -> str:
        """
        Extract toàn bộ text từ file CV.

        Args:
            file_path: đường dẫn tuyệt đối tới file trên disk

        Returns:
            Text đã extract và clean.

        Raises:
            ParseError: nếu file type không hỗ trợ hoặc parse thất bại
        """
        ext = detect_file_type(file_path)

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext in (".docx", ".doc"):
            return self._parse_docx(file_path)
        else:
            raise ParseError(
                code="UNSUPPORTED_FILE_TYPE",
                message="Chi ho tro file .pdf hoac .docx.",
                detail={"file_path": file_path, "extension": ext},
            )

    def _parse_pdf(self, file_path: str) -> str:
        """
        PDF pipeline:
          PDFParser (pypdf) → nếu text quá ngắn → OCRParser fallback
        """
        # Bước 1: thử extract text thường
        try:
            text = self._pdf_parser.parse(file_path)
        except ParseError:
            # PDFParser thất bại hoàn toàn → thử OCR luôn
            logger.warning(
                "PDFParser that bai voi '%s', chuyen sang OCR.", file_path
            )
            return self._ocr_parser.parse(file_path)

        # Bước 2: kiểm tra có đủ text không
        if len(text.strip()) >= _OCR_FALLBACK_THRESHOLD:
            logger.debug(
                "PDFParser OK: '%s' (%d ky tu).", file_path, len(text)
            )
            return text

        # Bước 3: text quá ngắn → PDF scan, fallback OCR
        logger.info(
            "PDF '%s' co it text (%d ky tu), fallback OCR.", file_path, len(text)
        )
        return self._ocr_parser.parse(file_path)

    def _parse_docx(self, file_path: str) -> str:
        return self._docx_parser.parse(file_path)


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[dict]:
    """
    Chia text thành các chunk để embed vào Qdrant.
    Word-based chunking với sliding window overlap.

    Args:
        text:       toàn bộ text của CV (output từ CVParser.parse)
        chunk_size: số words mỗi chunk (default 300)
        overlap:    số words overlap giữa 2 chunk liên tiếp (default 50)

    Returns:
        List[dict] với keys: chunk_index, content, token_count
        Ví dụ: [{"chunk_index": 0, "content": "...", "token_count": 280}, ...]
    """
    words = text.split()
    if not words:
        return []

    chunks: list[dict] = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]

        chunks.append({
            "chunk_index": len(chunks),
            "content": " ".join(chunk_words),
            "token_count": len(chunk_words),
        })

        if end >= len(words):
            break

        start = end - overlap

    return chunks