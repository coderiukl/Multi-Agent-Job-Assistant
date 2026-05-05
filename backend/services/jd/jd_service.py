from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException

from services.jd.regex_parser import (
    extract_jd_regex,
    extract_location,
    extract_salary,
    extract_seniority,
    extract_skills,
)
from services.llm_extractor import OLLAMA_BASE_URL, OLLAMA_MODEL

MAX_JD_TEXT_LENGTH = 20_000
LLM_CONTEXT_LIMIT = 8_000

VALID_JOB_TYPES = {"full-time", "part-time", "contract", "internship"}
VALID_SENIORITIES = {"intern", "fresher", "junior", "mid", "senior", "lead", "manager"}


@dataclass
class JDResult:
    raw_text: str
    title: str = "Unknown Position"
    department: Optional[str] = None
    location: Optional[str] = None
    job_type: str = "full-time"
    seniority: Optional[str] = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    extraction_method: str = "llm"


_JD_SYSTEM_PROMPT = """
You are a precise Job Description parser for an HR matching platform.
Return ONLY a valid JSON object. Do not return markdown, backticks, or explanations.

Schema:
{
  "title": "string",
  "department": "string or null",
  "location": "string or null",
  "job_type": "full-time | part-time | contract | internship",
  "seniority": "intern | fresher | junior | mid | senior | lead | manager | null",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "responsibilities": ["string"],
  "requirements": ["string"],
  "benefits": ["string"],
  "salary_min": number or null,
  "salary_max": number or null,
  "salary_currency": "VND | USD | null"
}

Rules:
- Keep responsibilities, requirements, and benefits in the original language.
- Do not hallucinate. Only extract information present in the JD.
- Normalize common skills, for example "js" -> "JavaScript", "postgres" -> "PostgreSQL".
- If salary is written as "20-30 trieu", return 20000000 and 30000000 with VND.
- Missing scalar fields must be null. Missing list fields must be [].
""".strip()


def process_jd_text(raw_text: str) -> JDResult:
    text = normalize_jd_text(raw_text)

    if not text:
        raise HTTPException(status_code=422, detail="JD content is empty.")

    if len(text) > MAX_JD_TEXT_LENGTH:
        raise HTTPException(status_code=413, detail="JD content is too long.")

    llm_output = _extract_jd_with_llm(text)
    _unload_ollama_model()

    if llm_output:
        result = _normalize_jd_output(llm_output, text, extraction_method="llm")
        _backfill_missing_fields(result)
        return result

    print("[JD] Falling back to regex extraction")
    result = _normalize_jd_output(
        extract_jd_regex(text),
        text,
        extraction_method="regex",
    )
    _backfill_missing_fields(result)
    return result


def normalize_jd_text(text: str) -> str:
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def build_jd_embedding_documents(jd: JDResult) -> list[dict]:
    documents = []
    profile_text = "\n".join(
        part
        for part in [
            f"Title: {jd.title}" if jd.title else "",
            f"Department: {jd.department}" if jd.department else "",
            f"Location: {jd.location}" if jd.location else "",
            f"Job type: {jd.job_type}" if jd.job_type else "",
            f"Seniority: {jd.seniority}" if jd.seniority else "",
        ]
        if part
    )

    if profile_text:
        documents.append({"field": "profile", "text": profile_text})

    if jd.required_skills:
        documents.append({"field": "required_skills", "text": ", ".join(jd.required_skills)})

    if jd.preferred_skills:
        documents.append({"field": "preferred_skills", "text": ", ".join(jd.preferred_skills)})

    if jd.requirements:
        documents.append({"field": "requirements", "text": "\n".join(jd.requirements)})

    if jd.responsibilities:
        documents.append({"field": "responsibilities", "text": "\n".join(jd.responsibilities)})

    if jd.benefits:
        documents.append({"field": "benefits", "text": "\n".join(jd.benefits)})

    return documents


def build_jd_embedding_text(jd: JDResult) -> str:
    return "\n\n".join(
        document["text"]
        for document in build_jd_embedding_documents(jd)
        if document.get("text")
    )


def _extract_jd_with_llm(raw_text: str) -> Optional[dict]:
    try:
        import requests

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": _JD_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text[:LLM_CONTEXT_LIMIT]},
                ],
                "options": {
                    "temperature": 0,
                    "num_predict": 2048,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        return _parse_json_response(content)
    except Exception as e:
        print(f"[JD LLM] Error: {e}")
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        return None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None


def _unload_ollama_model() -> None:
    try:
        import requests

        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "keep_alive": 0},
            timeout=10,
        )
    except Exception as e:
        print(f"[LLM] Unload warning: {e}")


def _normalize_jd_output(raw: dict, raw_text: str, extraction_method: str) -> JDResult:
    salary_min = _safe_int(raw.get("salary_min"))
    salary_max = _safe_int(raw.get("salary_max"))

    if salary_min and salary_max and salary_min > salary_max:
        salary_min, salary_max = salary_max, salary_min

    return JDResult(
        raw_text=raw_text,
        title=str(raw.get("title") or "").strip() or "Unknown Position",
        department=_none_or_str(raw.get("department")),
        location=_none_or_str(raw.get("location")),
        job_type=_normalize_job_type(raw.get("job_type")),
        seniority=_normalize_seniority(raw.get("seniority")),
        required_skills=_dedupe(_to_str_list(raw.get("required_skills"))),
        preferred_skills=_dedupe(_to_str_list(raw.get("preferred_skills"))),
        responsibilities=_to_str_list(raw.get("responsibilities")),
        requirements=_to_str_list(raw.get("requirements")),
        benefits=_to_str_list(raw.get("benefits")),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=_normalize_currency(raw.get("salary_currency")),
        extraction_method=extraction_method,
    )


def _backfill_missing_fields(jd: JDResult) -> None:
    if not jd.required_skills:
        jd.required_skills = extract_skills(jd.raw_text)

    if not jd.seniority:
        jd.seniority = extract_seniority(jd.raw_text)

    if not jd.location:
        jd.location = extract_location(jd.raw_text)

    if not jd.salary_min and not jd.salary_max:
        jd.salary_min, jd.salary_max, jd.salary_currency = extract_salary(jd.raw_text)


def _to_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    return _dedupe(
        str(item).strip(" -*\t\r\n")
        for item in value
        if item is not None
    )


def _none_or_str(value) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).lower()
    multiplier = 1

    if "trieu" in text or "million" in text:
        multiplier = 1_000_000
    elif re.search(r"\bk\b", text):
        multiplier = 1_000

    numbers = re.findall(r"\d+(?:[.,]\d+)?", text)
    if not numbers:
        return None

    return int(float(numbers[0].replace(",", ".")) * multiplier)


def _normalize_job_type(value) -> str:
    text = str(value or "").lower().strip().replace("_", "-")
    mapping = {
        "full time": "full-time",
        "fulltime": "full-time",
        "part time": "part-time",
        "parttime": "part-time",
        "intern": "internship",
        "contractor": "contract",
    }

    normalized = mapping.get(text, text)
    return normalized if normalized in VALID_JOB_TYPES else "full-time"


def _normalize_seniority(value) -> Optional[str]:
    text = str(value or "").lower().strip()
    mapping = {
        "middle": "mid",
        "entry": "junior",
        "entry-level": "junior",
        "internship": "intern",
    }

    normalized = mapping.get(text, text)
    return normalized if normalized in VALID_SENIORITIES else None


def _normalize_currency(value) -> Optional[str]:
    text = str(value or "").upper().strip()

    if text in {"VND", "USD"}:
        return text

    return None


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
