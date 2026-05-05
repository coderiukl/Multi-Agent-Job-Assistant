from __future__ import annotations

import json
import re

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"

_PROMPT_TEMPLATE = """\
You are a precise CV/resume parser. Extract structured information from the CV text below.

Return ONLY a valid JSON object with this exact schema (no markdown, no explaination):
{{
    "full_name": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "location": "string or null",
    "summary": "string or null",
    "skills": {{
        "CategoryName": ["skill1", "skill2"]
    }},
    "work_experience": [
        {{
            "title": "string or null",
            "company": "string or null",
            "date": "string or null",
            "responsibilities": ["string"]
        }}
    ],
    "projects": [
        {{
            "title": "string or null",
            "date": "string or null",
            "tools": ["string"],
            "descriptions": ["string"]
        }}
    ],
    "education": [
        {{
            "school": "string or null",
            "degree": "string or null",
            "major": "string or null",
            "date": "string or null",
            "descriptions": ["string"]
        }}
    ]
}}

Rules:
- Keep original language (Vietnamese or English) for all values
- If a field is missing, use null (not empty string)
- For skills: group by category if evident, else use "General" as key
- Do not hallucinate - only extract what is explicity in the text

CV_TEXT:
{cv_text}\
"""

def extract_with_llm(cv_text: str) -> dict | None:
    """
    Gọi Ollama để parse CV text -> dict.
    Trả None nếu Ollama không chạy hoặc output không parse được.
    """
    prompt = _PROMPT_TEMPLATE.format(cv_text=cv_text[:12000]) # Tránh vượt context window
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2048,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return _parse_json_response(raw)
    except Exception as e:
        print(f"[LLM] Ollama unavailable or error: {e}")
        return None

def normalize_llm_output(data: dict) -> dict:
    """Chuẩn hóa output LLM về đúng schema, fill default nếu thiếu key."""
    return {
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "location": data.get("location"),
        "summary": data.get("summary") or "",
        "skills": data.get("skills") or {},
        "work_experience": data.get("work_experience") or [],
        "projects": data.get("projects") or [],
        "education": data.get("education") or [],
    }

def _parse_json_response(text: str) -> dict | None:
    """Bỏ markdown fence nếu model wrap trong ```json```, rồi parse."""
    raw = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
