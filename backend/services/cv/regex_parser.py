import re

def normalize_cv_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    lines = []
    for line in text.splitlines():
        line = _normalize_cv_line(line)
        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def _normalize_cv_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\s•◦▪▫*«»©§|]+", "", line)
    line = re.sub(r"[\s•◦▪▫*«»©§|]+$", "", line)
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()

def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else None

def _extract_phone(text: str) -> str | None:
    pattern = r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?!\w)"

    for match in re.finditer(pattern, text):
        phone = match.group(0).strip()
        digits = re.sub(r"\D", "", phone)

        if 8 <= len(digits) <= 15:
            return phone
    
    return None

def _extract_full_name(text: str) -> str | None:
    lines = _get_clean_lines(text)

    for line in lines[:8]:
        if "@" in line or re.search(r"\d", line):
            continue

        lowered = line.lower()
        if any(word in lowered for word in ["summary", "objective", "education", "skills", "project", "experience"]):
            continue

        if 2 <= len(line.split()) <= 6:
            return line

    return None

def _extract_location(text: str) -> str | None:
    lines = _get_clean_lines(text)

    for line in lines[:15]:
        lowered = line.lower()

        if "@" in line:
            parts = re.split(r"\s{2,}|(?<=\.com)\s+", line)
            for part in parts:
                if any(k in part.lower() for k in ["city", "ward", "district", "ho chi minh", "hanoi", "da nang"]):
                    return part.strip()

        if any(k in lowered for k in ["city", "ward", "district", "province", "ho chi minh", "hanoi", "da nang"]):
            phone = _extract_phone(line)
            email = _extract_email(line)
            cleaned = line
            if phone:
                cleaned = cleaned.replace(phone, "")
            if email:
                cleaned = cleaned.replace(email, "")
            cleaned = re.sub(r"^[^\wÀ-ỹ]+", "", cleaned).strip()
            return cleaned or line

    return None

def _extract_education(text: str) -> list[dict]:
    if not text:
        return []
    
    blocks = _split_blocks(text)
    items = []

    for block in blocks:
        lines = _get_clean_lines(block)

        if not lines:
            continue

        item = {
            "school": None,
            "degree": None,
            "major": None,
            "date": _extract_date_range(block),
            "gpa": _extract_gpa(block),
            "descriptions": lines,
        }

        for line in lines:
            lowered = line.lower()

            if any(word in lowered for word in ["university", "college", "institute", "school", "đại học", "cao đẳng", "học viện"]):
                item['school'] = line

            if any(word in lowered for word in ["bachelor", "engineer", "master", "degree", "cử nhân", "kỹ sư", "thạc sĩ"]):
                item['degree'] = line
            
            if any(word in lowered for word in ["data science", "computer science", "software", "information technology", "khoa học dữ liệu", "công nghệ thông tin"]):
                item['major'] = line
            
        items.append(item)

    return items

KNOWN_SKILL_CATEGORIES = {
    "web development",
    "databases",
    "version control",
    "responsive web",
    "system integration",
    "iot",
    "frontend",
    "backend",
    "database",
    "programming languages",
    "frameworks",
    "tools",
}

def _extract_skills(text: str) -> dict:
    if not text:
        return {}

    skills: dict[str, list[str]] = {}

    for line in _get_clean_lines(text):
        lowered = line.lower()

        matched_category = None
        for category in KNOWN_SKILL_CATEGORIES:
            if lowered.startswith(category):
                matched_category = category.title()
                value = line[len(category):].strip(" :-")
                break

        if matched_category:
            skills[matched_category] = _split_skill_items(value)
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            skills[key.strip()] = _split_skill_items(value)
        else:
            skills.setdefault("General", []).extend(_split_skill_items(line))

    return {
        key: list(dict.fromkeys(value))
        for key, value in skills.items()
        if value
    }

def _extract_work_experience(text: str) -> list[dict]:
    if not text:
        return []
    
    blocks = _split_blocks(text)
    experiences = []

    for block in blocks:
        lines = _get_clean_lines(block)

        if not lines:
            continue

        experiences.append({
            "title": lines[0],
            "company": _guess_company(lines),
            "date": _extract_date_range(block),
            "responsibilities": lines[1:],
        })

    return experiences

def _extract_projects(text: str) -> list[dict]:
    if not text:
        return []

    lines = _get_clean_lines(text)

    if not lines:
        return []

    project_blocks = _split_project_blocks(lines)
    projects = []

    for block_lines in project_blocks:
        raw_title = block_lines[0]
        title, date = _extract_project_title_and_date(raw_title)

        block_text = "\n".join(block_lines)

        if not date:
            date = _extract_date_range(block_text)

        tools = []
        descriptions = []

        for line in block_lines[1:]:
            lowered = line.lower()

            if is_date_line(line):
                continue

            if (
                lowered.startswith("tools:")
                or lowered.startswith("technologies:")
                or lowered.startswith("tech stack:")
            ):
                tools = _split_skill_items(line.split(":", 1)[1])
                continue

            descriptions.append(line)

        projects.append({
            "title": title,
            "date": date,
            "tools": tools,
            "descriptions": descriptions,
        })

    return projects

def _extract_project_title_and_date(line: str) -> tuple[str, str | None]:
    date = _extract_date_range(line)
    title = line

    if date:
        title = title[:line.lower().find(date.lower())].strip()

    title = re.sub(r"\s*\|\s*LINK\s*$", "", title, flags=re.I)
    title = title.strip(" |:-–—")

    return title, date



def _split_project_blocks(lines: list[str]) -> list[list[str]]:
    title_indexes = []

    for index, line in enumerate(lines):
        if _is_project_title_line(lines, index):
            title_indexes.append(index)

    if not title_indexes:
        return [lines]

    blocks = []

    for position, start_index in enumerate(title_indexes):
        end_index = (
            title_indexes[position + 1]
            if position + 1 < len(title_indexes)
            else len(lines)
        )

        blocks.append(lines[start_index:end_index])

    return blocks

def _is_project_title_line(lines: list[str], index: int) -> bool:
    line = lines[index].strip()
    lowered = line.lower()

    if not line:
        return False

    if line.startswith(("+", "-", "•", "*")):
        return False

    if is_date_line(line):
        return False

    if lowered.startswith(("tools:", "technologies:", "tech stack:")):
        return False

    if line.endswith("."):
        return False

    description_starts = (
        "web developer",
        "backend developer",
        "frontend developer",
        "fullstack developer",
        "responsible",
        "reponsible",
        "contributed",
        "participated",
        "developed",
        "implemented",
        "integrated",
        "managed",
        "built",
        "created",
        "designed",
        "applied",
        "performed",
        "conducted",
        "identified",
        "enhanced",
        "optimized",
        "supported",
        "factory",
        "transportation and",
    )

    if lowered.startswith(description_starts):
        return False

    title, date = _extract_project_title_and_date(line)

    if date:
        word_count = len(title.split())
        return 2 <= word_count <= 16

    next_lines = lines[index + 1:index + 5]
    has_date_soon = any(_extract_date_range(next_line) for next_line in next_lines)

    word_count = len(line.split())

    if has_date_soon and 2 <= word_count <= 16:
        return True

    return False

def _clean_section(text: str) -> str:
    return normalize_cv_text(text)


def _get_clean_lines(text: str) -> list[str]:
    return [
        line.strip(" \t•◦▪▫*-–—«»©@")
        for line in text.splitlines()
        if line.strip(" \t•◦▪▫*-–—«»©@")
    ]


def _split_blocks(text: str) -> list[str]:
    blocks = re.split(r"\n\s*(?:•|◦|▪|▫|\*|-|–|—|«|©)\s+", "\n" + text)
    blocks = [block.strip() for block in blocks if block.strip()]

    if len(blocks) <= 1:
        blocks = re.split(r"\n{2,}", text)

    return [block.strip() for block in blocks if block.strip()]


def _split_skill_items(text: str) -> list[str]:
    items = re.split(r",|;|\||/", text)

    return [
        item.strip()
        for item in items
        if item.strip()
    ]


def _extract_date_range(text: str) -> str | None:
    month = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?"
    )

    patterns = [
        rf"\b(?:{month})\s*-\s*\d{{4}}\s*-\s*(?:Present|Now|\d{{4}})\b",
        rf"\b(?:{month})\s*-\s*(?:{month})\s*-\s*\d{{4}}\b",
        rf"\b(?:{month})\s+\d{{4}}\s*-\s*(?:{month})\s+\d{{4}}\b",
        rf"\b(?:{month})\s+\d{{4}}\s*-\s*(?:Present|Now)\b",
        rf"\b(?:{month})\s*-\s*(?:Present|Now)\b",
        r"\b\d{4}\s*-\s*(?:Present|Now|\d{4})\b",
        r"\b\d{1,2}/\d{4}\s*-\s*(?:Present|Now|\d{1,2}/\d{4})\b",
        r"\b\d{4}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0).strip()

    return None

def _extract_gpa(text: str) -> str | None:
    patterns = [
        r"\bGPA\s*(?:of|:)?\s*([\d.]+)\s*/\s*([\d.]+)",
        r"\bGPA\s*(?:of|:)?\s*([\d.]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            if len(match.groups()) == 2 and match.group(2):
                return f"{match.group(1)}/{match.group(2)}"
            return match.group(1)

    return None


def is_date_line(line: str) -> bool:
    return _extract_date_range(line) == line


def _guess_company(lines: list[str]) -> str | None:
    for line in lines[1:4]:
        lowered = line.lower()

        if any(word in lowered for word in ["company", "corp", "ltd", "inc", "co.", "công ty"]):
            return line

    return None

def _split_cv_sections(text: str) -> dict:
    section_aliases = {
        "summary": [
            "SUMMARY",
            "PROFILE",
            "ABOUT ME",
            "OBJECTIVE",
            "CAREER OBJECTIVE",
            "PROFESSIONAL SUMMARY",
            "TÓM TẮT",
            "MỤC TIÊU",
            "MỤC TIÊU NGHỀ NGHIỆP",
        ],
        "education": [
            "EDUCATION",
            "ACADEMIC BACKGROUND",
            "QUALIFICATIONS",
            "HỌC VẤN",
            "TRÌNH ĐỘ HỌC VẤN",
            "GIÁO DỤC",
        ],
        "skills": [
            "SKILLS",
            "SKILLS SUMMARY",
            "TECHNICAL SKILLS",
            "CORE SKILLS",
            "KEY SKILLS",
            "KỸ NĂNG",
            "KỸ NĂNG CHUYÊN MÔN",
        ],
        "work_experience": [
            "EXPERIENCE",
            "WORK EXPERIENCE",
            "EMPLOYMENT HISTORY",
            "PROFESSIONAL EXPERIENCE",
            "KINH NGHIỆM",
            "KINH NGHIỆM LÀM VIỆC",
        ],
        "projects": [
            "PROJECTS",
            "PERSONAL PROJECTS",
            "ACADEMIC PROJECTS",
            "DỰ ÁN",
            "DỰ ÁN CÁ NHÂN",
        ],
        "certificates": [
            "CERTIFICATE",
            "CERTIFICATES",
            "CERTIFICATION",
            "CERTIFICATIONS",
            "CHỨNG CHỈ",
        ],
    }

    heading_to_keys = {}

    for key, aliases in section_aliases.items():
        for alias in aliases:
            heading_to_keys[alias.upper()] = key

    all_headings = sorted(heading_to_keys.keys(), key=len, reverse=True)

    pattern = r"(?mi)^\s*(" + "|".join(re.escape(h) for h in all_headings) + r")\s*[:@#•◦▪▫*«»©-]*\s*$"
    matches = list(re.finditer(pattern, text))

    sections = {
        "summary": "",
        "education": "",
        "skills": "",
        "work_experience": "",
        "projects": "",
        "certificates": "",
    }

    for index, match in enumerate(matches):
        heading = match.group(1).upper()
        key = heading_to_keys[heading]

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        content = text[start:end].strip()

        if sections[key]:
            sections[key] += "\n" + content
        else:
            sections[key] = content

    return sections 

def extract_cv_details(text: str) -> dict:
    sections = _split_cv_sections(text)
    return {
        "full_name": _extract_full_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "location": _extract_location(text),
        "summary": _clean_section(sections.get("summary", "")),
        "education": _extract_education(sections.get("education", "")),
        "skills": _extract_skills(sections.get("skills", "")),
        "work_experience": _extract_work_experience(sections.get("work_experience", "")),
        "projects": _extract_projects(sections.get("projects", "")),
    }      

def extract_cv_details_regex(text: str) -> dict:
    """Alias để cv_service.py gọi fallback rõ ràng hơn."""
    return extract_cv_details(text)
