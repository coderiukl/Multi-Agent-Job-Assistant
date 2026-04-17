# 🚀 Job Search Agent - Multi-Agent Job Assistant System

Hệ thống AI hỗ trợ tìm kiếm việc làm thông minh, sử dụng **Multi-Agent + Vector Search (RAG)** để kết nối CV với job phù hợp.

---

## 🧠 Kiến trúc hệ thống (System Architecture)

Hệ thống được thiết kế theo mô hình **Multi-Agent Pipeline**:

```
User Input (CV / Query)
        ↓
   Router Agent
        ↓
 ┌───────────────┬────────────────┐
 │               │                │
CV Parser   Job Matcher      Web Scraper (future)
 │               │
 ↓               ↓
Embedding      Vector Search (Qdrant)
 │               │
 └──────→ Ranking + Filtering
                ↓
           Final Response
```

---

## ⚙️ Core Features

* 📄 **CV Parsing Agent**

  * Trích xuất thông tin từ PDF / DOCX / Text
  * OCR với Tesseract nếu cần

* 🔍 **Job Matching Agent**

  * So khớp CV với job bằng embeddings
  * Hybrid search (Vector + Metadata)

* 🤖 **Multi-Agent Orchestration**

  * Sử dụng LangGraph để điều phối flow
  * Dễ mở rộng thêm agent mới

* 🧠 **Semantic Search**

  * Qdrant vector database
  * Embedding đa ngôn ngữ (EN + VI)

* 👤 **Authentication**

  * JWT-based login/register

---

## 🧩 Tech Stack

| Thành phần    | Công nghệ                      |
| ------------- | ------------------------------ |
| Backend       | FastAPI                        |
| Orchestration | LangGraph + LangChain          |
| Database      | PostgreSQL                     |
| Vector DB     | Qdrant                         |
| Cache         | Redis                          |
| Embedding     | Sentence Transformers / BGE-M3 |
| OCR           | Tesseract                      |
| Deployment    | Docker Compose                 |

---

## 🔄 Data Flow

### 1. Upload CV

```text
User → API → CV Parser → Clean Text → Embedding → Qdrant
```

### 2. Job Matching

```text
User Query → Embedding → Qdrant Search → Ranking → Response
```

### 3. Hybrid Matching

```text
Vector Search (Qdrant)
        +
Metadata Filter (Postgres)
        ↓
Final Jobs
```

---

## 🗄️ Database Design

### PostgreSQL (Relational)

* Users
* Conversations
* Messages
* Jobs (metadata)

👉 Dùng để:

* Lưu user & auth
* Lưu lịch sử chat
* Lọc job theo metadata

---

### Qdrant (Vector DB)

* Lưu embeddings của:

  * Jobs
  * CV

👉 Dùng để:

* Semantic search
* Similarity matching

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py
│   │
│   ├── core/
|   |   ├── llm.py
│   │   ├── cache.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   └── models.py
│   │
│   ├── agents/                  # Multi-Agent Layer
│   │   ├── state.py
│   │   ├── intent.py
│   │   ├── cv_advisor.py
│   │   ├── matcher.py
│   │   ├── responder.py
│   │   └── workflow.py
│   │
│   ├── services/               # Business Logic
│   │   ├── embedding_service.py
│   │   ├── qdrant_services.py
│   │   ├── job_matcher.py
│   │   └── cv_parser.py
│   │
│   ├── routers/                # API Layer
│   │   ├── auth.py
│   │   ├── cv.py
│   │   ├── conversation.py
│   │   └── match.py
│   │
│   ├── schemas/
│   │
│   └── parsers/
│       ├── pdf_parser.py
│       ├── docx_parser.py
│       ├── ocr_parser.py
│       ├── cv_parser.py
│       └── text_cleaner.py
│
├── scripts/
│   └── seed_jobs.py
│
├── data/
│   └── VietJobs.csv
│
├── uploads/
│   └── cvs/
│
├── alembic/
├── docker-compose.yml
└── requirements.txt
```

---

## 🤖 Multi-Agent Logic

### Router Agent

* Xác định intent của user:

  * Upload CV → CV Agent
  * Search job → Matcher Agent

---

### CV Agent

* Parse CV
* Extract:

  * Skills
  * Experience
  * Education
* Generate embedding

---

### Matcher Agent

* Nhận:

  * CV embedding hoặc query
* Gọi:

  * Qdrant search
  * Postgres filter
* Trả:

  * Top jobs phù hợp

---

## 🚀 Setup & Run

### 1. Clone project

```bash
git clone https://github.com/coderiukl/Multi-Agent-Job-Assistant.git
cd job-search-agent
```

---

### 2. Setup environment

```bash
cd backend
cp .env.example .env
```

---

### 3. Run Docker

```bash
docker compose up -d
```

---

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 5. Migrate DB

```bash
alembic upgrade head
```

---

### 6. Seed data

```bash
python -m scripts.seed_jobs --file data/VietJobs.csv
```

---

### 7. Run server

```bash
uvicorn app.main:app --reload
```

---

## 🔍 API Docs

* Swagger: http://localhost:8000/docs

---

## 🧪 Example Use Cases

### 1. Upload CV

→ System phân tích CV → gợi ý job

### 2. Chat với AI

→ Hỏi:

* "Tôi phù hợp công việc gì?"
* "Cần học gì để làm backend?"

---

## Future Improvements

* 🌐 Web scraping job realtime
* 🧠 LLM reasoning (Gemini/OpenAI)
* 📊 Ranking model learning
* 🧾 CV optimization suggestions
* 🔁 Feedback loop training

---

## 📌 Notes

* Hệ thống hỗ trợ **đa ngôn ngữ (VI + EN)**
* Embedding khuyến nghị: `bge-m3`

