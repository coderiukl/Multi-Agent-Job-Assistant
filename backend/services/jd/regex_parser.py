from __future__ import annotations

import re
from typing import Optional

KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "C#", "C++",
    "React", "Next.js", "Vue", "Angular", "Node.js", "Express", "NestJS",
    "FastAPI", "Django", "Flask", "Spring Boot", ".NET",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQL Server",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Linux", "Git",
    "Machine Learning", "Deep Learning", "NLP", "LLM", "RAG",
    "Qdrant", "Elasticsearch", "Kafka", "RabbitMQ",
]


def extract_jd_regex(raw_text: str) -> dict:
    sections = split_sections(raw_text)
    lines = clean_lines(raw_text)

    required_text = sections.get("requirements") or raw_text
    responsibility_text = sections.get("responsibilities") or ""
    benefit_text = sections.get("benefits") or ""
    salary_min, salary_max, currency = extract_salary(raw_text)

    return {
        "title": extract_title(lines),
        "department": extract_department(raw_text),
        "location": extract_location(raw_text),
        "job_type": extract_job_type(raw_text),
        "seniority": extract_seniority(raw_text),
        "required_skills": extract_skills(required_text),
        "preferred_skills": extract_preferred_skills(raw_text),
        "responsibilities": extract_bullets(responsibility_text),
        "requirements": extract_bullets(required_text),
        "benefits": extract_bullets(benefit_text),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
    }


def split_sections(text: str) -> dict[str, str]:
    aliases = {
        "responsibilities": [
            "responsibilities", "job description", "what you will do",
            "mo ta cong viec", "trach nhiem", "nhiem vu",
        ],
        "requirements": [
            "requirements", "qualifications", "what we expect",
            "yeu cau", "yeu cau cong viec", "ky nang yeu cau",
        ],
        "benefits": [
            "benefits", "perks", "why join us",
            "quyen loi", "phuc loi", "dai ngo",
        ],
    }

    heading_to_key = {
        heading.lower(): key
        for key, headings in aliases.items()
        for heading in headings
    }
    pattern = r"(?mi)^\s*(" + "|".join(re.escape(h) for h in heading_to_key) + r")\s*[:\-]?\s*$"
    matches = list(re.finditer(pattern, text))

    sections = {
        "summary": text,
        "responsibilities": "",
        "requirements": "",
        "benefits": "",
    }

    if not matches:
        return sections

    sections["summary"] = text[:matches[0].start()].strip()

    for index, match in enumerate(matches):
        key = heading_to_key[match.group(1).lower()]
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[key] = text[start:end].strip()

    return sections


def clean_lines(text: str) -> list[str]:
    return [
        line.strip(" -*\t")
        for line in text.splitlines()
        if line.strip(" -*\t")
    ]


def extract_title(lines: list[str]) -> str:
    for line in lines[:8]:
        lowered = line.lower()
        if any(k in lowered for k in ["salary", "luong", "location", "dia diem", "benefit"]):
            continue
        if 2 <= len(line.split()) <= 12:
            return line

    return lines[0] if lines else "Unknown Position"


def extract_department(text: str) -> Optional[str]:
    match = re.search(r"(?im)^\s*(department|phong ban)\s*[:\-]\s*(.+)$", text)
    return match.group(2).strip() if match else None


def extract_location(text: str) -> Optional[str]:
    match = re.search(r"(?im)^\s*(location|dia diem|noi lam viec)\s*[:\-]\s*(.+)$", text)
    if match:
        return match.group(2).strip()

    known_locations = [
        "Ho Chi Minh", "HCM", "TP.HCM", "Ha Noi", "Da Nang", "Remote", "Hybrid",
    ]
    lowered = text.lower()

    for location in known_locations:
        if location.lower() in lowered:
            return location

    return None


def extract_job_type(text: str) -> str:
    lowered = text.lower()

    if re.search(r"part[- ]?time|ban thoi gian", lowered):
        return "part-time"
    if re.search(r"contract|hop dong", lowered):
        return "contract"
    if re.search(r"internship|intern|thuc tap", lowered):
        return "internship"

    return "full-time"


def extract_seniority(text: str) -> Optional[str]:
    lowered = text.lower()
    patterns = [
        ("manager", r"\bmanager\b|quan ly"),
        ("lead", r"\blead\b|tech lead|team lead"),
        ("senior", r"\bsenior\b|sr\.|cao cap"),
        ("mid", r"\bmid\b|\bmiddle\b|trung cap"),
        ("junior", r"\bjunior\b|jr\.|entry[- ]level"),
        ("fresher", r"\bfresher\b|moi tot nghiep"),
        ("intern", r"\bintern\b|internship|thuc tap"),
    ]

    for value, pattern in patterns:
        if re.search(pattern, lowered):
            return value

    return None


def extract_skills(text: str) -> list[str]:
    found = []

    for skill in KNOWN_SKILLS:
        pattern = r"(?<![\w.+#-])" + re.escape(skill) + r"(?![\w.+#-])"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill)

    aliases = {
        "js": "JavaScript",
        "ts": "TypeScript",
        "postgres": "PostgreSQL",
        "k8s": "Kubernetes",
        "ml": "Machine Learning",
    }
    lowered = text.lower()

    for alias, canonical in aliases.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", lowered):
            found.append(canonical)

    return dedupe(found)


def extract_preferred_skills(text: str) -> list[str]:
    patterns = [
        r"(?is)(nice to have|preferred|uu tien|loi the)[:\-\s]+(.{0,800})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return extract_skills(match.group(2))

    return []


def extract_bullets(text: str) -> list[str]:
    bullets = []

    for line in clean_lines(text):
        if len(line) < 3:
            continue
        if re.match(r"^[A-Z\s]{4,}:?$", line):
            continue
        bullets.append(line)

    return bullets[:20]


def extract_salary(text: str) -> tuple[Optional[int], Optional[int], Optional[str]]:
    lowered = text.lower()
    currency = None

    if re.search(r"\busd\b|\$", lowered):
        currency = "USD"
    elif re.search(r"vnd|vnd|trieu|dong", lowered):
        currency = "VND"

    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*(?:-|~|to)\s*(\d+(?:[.,]\d+)?)\s*(trieu|m|million|usd|\$|vnd)?",
        r"up to\s*(\d+(?:[.,]\d+)?)\s*(trieu|m|million|usd|\$|vnd)?",
        r"toi\s*(\d+(?:[.,]\d+)?)\s*(trieu|m|million|usd|\$|vnd)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue

        groups = match.groups()
        numbers = [g for g in groups[:2] if g and re.search(r"\d", g)]
        unit = groups[-1] or ""
        multiplier = 1

        if unit in {"trieu", "m", "million"}:
            multiplier = 1_000_000
            currency = currency or "VND"

        parsed = [int(float(number.replace(",", ".")) * multiplier) for number in numbers]

        if len(parsed) == 1:
            return None, parsed[0], currency
        if len(parsed) >= 2:
            return min(parsed), max(parsed), currency

    return None, None, currency


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
