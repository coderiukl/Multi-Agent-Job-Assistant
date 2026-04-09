from __future__ import annotations

import os 

import pytesseract

def config_tesseract(tesseract_cmd: str | None = None) -> None:
    cmd = tesseract_cmd or os.getenv("TESSRACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd