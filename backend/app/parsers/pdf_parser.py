from __future__ import annotations

from pypdf import PdfReader

from app.parsers.utils import ParseError

class PDFParser:
    def parse(self, file_path: str) -> str:
        try:
            reader = PdfReader(file_path)
        except Exception as exc:
            raise ParseError(
                code="PDF_OPEN_FAILED",
                message="Không mở được file này",
                detail={"file_path": file_path, "error": str(exc)}
            ) from exc
        
        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
        return "\n".join(chunks).strip()