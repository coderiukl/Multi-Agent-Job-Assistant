from __future__ import annotations

from docx import Document
from app.parsers.utils import ParseError

class DOCXParser:
    def parse(self, file_path: str) -> str:
        try:
            doc = Document(file_path)
        except Exception as exc:
            raise ParseError(
                code="DOCX_OPEN_FAILED",
                message="Không mở được file DOCX",
                detail={"file_path": file_path, "error": str(exc)}
            ) from exc
        lines = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(lines).strip()
    
    