from __future__ import annotations

from pathlib import Path
import pytesseract
from PIL import Image

from app.parsers.utils import ParseError
from app.services.tesseract_config import config_tesseract

class OCRParser:
    SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

    def __init__(self, language: str = "eng+vie", tesseract_cmd: str | None = None):
        self.language = language
        config_tesseract(tesseract_cmd=tesseract_cmd)

    def parse(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._ocr_pdf(file_path=file_path)
        if ext in self.SUPPORTED_IMAGES:
            return self._ocr_image(file_path=file_path)
        raise ParseError(
            code="OCR_UNSUPPORTED_FILE_TYPE",
            message="OCR chỉ hỗ trợ PDF hoặc file ảnh.",
            detail={"file_path": file_path, "extension": ext},
        )
    
    def _ocr_image(self, file_path: str) -> str:
        try: 
            image = Image.open(file_path)
            return pytesseract.image_to_string(image, lang=self.language).strip()
        except Exception as exc:
            raise ParseError(
                code = "OCR_IMAGE_FAILED",
                message="OCR thất bại với file ảnh.",
                detail={"file_path": file_path, "error": str(exc)},
            ) from exc
        
    def _ocr_pdf(self, file_path: str) -> str:
        try:
            import fitz
        except Exception as exc:
            raise ParseError(
                code="OCR_ENGINE_MISSING",
                message="Thiếu PyMuPDF để OCR PDF.",
                detail={"error": str(exc)},
            ) from exc
        
        try:
            doc = fitz.open(file_path)
            chunks: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                mode = "RGBA" if pix.alpha else "RGB"
                image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(image, lang=self.language).strip()
                if text:
                    chunks.append(text)
            doc.close()
            return "\n".join(chunks).strip()
        except Exception as exc:
            raise ParseError(
                code="OCR_PDF_FAILED",
                message="OCR thất bại với file PDF.",
                detail={"file_path": file_path, "error": str(exc)},
            ) from exc
        