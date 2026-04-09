from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass
class ParseError(Exception):
    code: str
    message: str
    detail: dict | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail or {},
            "recoverable": True,
        }
    
def detect_file_type(file_path: str) -> str:
    return Path(file_path).suffix.lower()