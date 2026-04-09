# 📖 Job Search Agent - Architecture Documentation

Tài liệu này mô tả chi tiết luồng hoạt động của các module chính trong hệ thống.

## 📚 Danh sách tài liệu


### 1. 🔐 [Authentication Flow](./ARCHITECTURE_AUTH.md)
**Module: Auth**

Mô tả chi tiết luồng xác thực của hệ thống:
- **Đăng ký** (Register) - Tạo tài khoản mới
- **Đăng nhập** (Login) - Xác thực email + password → Access token + Refresh token
- **Làm mới token** (Refresh) - Cấp access token mới từ refresh token
- **Đăng xuất** (Logout) - Hủy hiệu lực refresh token
- **Lấy thông tin user** (Get Me) - Truy vấn thông tin user hiện tại

**Key Concepts:**
- JWT (JSON Web Tokens) - Access token ngắn hạn (30 phút)
- Refresh token dài hạn (7 ngày) - Hash lưu trong DB
- Token rotation - Revoke cũ khi refresh, prevent replay attacks
- Password hashing - Bcrypt, không lưu plain text

---

### 2. 📄 [CV Processing Pipeline](./ARCHITECTURE_CV.md)
**Module: CV**

Mô tả chi tiết luồng xử lý file CV:
- **Upload** (Upload) - Nhận file PDF/DOCX từ user
- **Parse** (Parsing) - Trích xuất text từ file
  - PDFParser (pypdf) - Extract text từ PDF
  - DOCXParser (python-docx) - Extract text từ DOCX
  - Fallback OCR - Detect scan PDFs, dùng Tesseract
- **Chunk** (Text Chunking) - Chia text thành các đoạn với overlap
- **Embed** (Embedding) - Chuyển text thành vectors 1024-dim
- **Danh sách** CVs - List tất cả CV của user
- **Chi tiết** CV - Xem CV + chunks

**Key Concepts:**
- File validation - Extension + size checks
- Text parsing strategies - Different approach per file type
- Sliding window chunking - Word-based, 300 words per chunk, 50-word overlap
- Sentence-Transformers - Model: BAAI/bge-m3 (multilingual, 1024-dim)
- Qdrant vector database - Store + search embeddings
- Status tracking - parsing → embedded → failed

---

### 3. 🎯 [Job Matching Pipeline](./ARCHITECTURE_MATCH.md)
**Module: Match**

Mô tả chi tiết luồng so khớp công việc:
- **Match CV vs JD** - So sánh CV với 1 mô tả công việc cụ thể
  - Embed JD text
  - Search tương tự trong CV chunks
  - Trả về overall score + matching chunks
- **Find Matching Jobs** - Tìm danh sách jobs phù hợp nhất với CV
  - Average CV chunks → representative vector
  - Search similar jobs trong job database
  - Trả về top K jobs sorted by score

**Key Concepts:**
- Semantic similarity - Cosine distance, 0-1 range
- Vector representation - Each document → 1024-dim vector
- Average pooling - Combine all chunks into 1 CV vector
- Two Qdrant collections - "cvs" + "jobs"
- Context-aware matching - Not keyword-based, meaning-based
- Multilingual support - Thanks to BAAI/bge-m3 model

---

## 🏗️ System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        USER                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Routers (API Endpoints)                            │   │
│  │  ├─ /auth      (register, login, logout, me)       │   │
│  │  ├─ /cvs       (upload, list, detail)              │   │
│  │  └─ /match     (cv-vs-jd, jobs)                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                            ↓                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Services (Business Logic)                          │   │
│  │  ├─ cv_parser       (Extract text from files)      │   │
│  │  ├─ embedding_service (Convert text → vectors)     │   │
│  │  ├─ search_services   (Find similar matches)       │   │
│  │  └─ qdrant_services   (Vector DB operations)       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
        ↓                           ↓                   ↓
        
┌──────────────────┐    ┌──────────────────┐   ┌──────────────┐
│  PostgreSQL      │    │    Qdrant        │   │    Redis     │
│  (Relational)    │    │  (Vector Search) │   │   (Cache)    │
│                  │    │                  │   │              │
│ - users          │    │ - cvs collection │   │ Future use   │
│ - files          │    │   (CV chunks)    │   │              │
│ - file_chunks    │    │ - jobs collection│   │              │
│ - jobs           │    │   (Job ads)      │   │              │
│ - refresh_tokens │    │                  │   │              │
└──────────────────┘    └──────────────────┘   └──────────────┘
```

---

## 🗂️ Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app entry point
│   │
│   ├── routers/
│   │   ├── auth.py    ────────────────→ ARCHITECTURE_AUTH.md
│   │   ├── cv.py      ────────────────→ ARCHITECTURE_CV.md
│   │   └── match.py   ────────────────→ ARCHITECTURE_MATCH.md
│   │
│   ├── services/
│   │   ├── cv_parser.py               # Parse PDF/DOCX
│   │   ├── embedding_service.py       # Transform text → vectors
│   │   ├── search_services.py         # Find similar items
│   │   ├── qdrant_services.py         # Vector DB ops
│   │   └── tesseract_config.py        # OCR config
│   │
│   ├── parsers/
│   │   ├── pdf_parser.py              # PyPDF + OCR fallback
│   │   ├── docx_parser.py             # python-docx
│   │   ├── ocr_parser.py              # Tesseract OCR
│   │   ├── text_cleaner.py            # Normalize text
│   │   └── utils.py                   # Helper functions
│   │
│   ├── db/
│   │   ├── models.py                  # SQLAlchemy models
│   │   └── base.py                    # Declarative base
│   │
│   ├── schemas/
│   │   ├── auth.py                    # Request/response models
│   │   ├── cv_jd.py
│   │   └── parse.py
│   │
│   └── core/
│       ├── config.py                  # Settings from .env
│       ├── dependencies.py            # Dependency injection
│       └── security.py                # JWT, password hashing
│
├── alembic/                            # Database migrations
│   └── versions/
│
├── scripts/
│   └── seed_jobs.py                   # Load jobs from CSV
│
└── docs/                               # 👈 YOU ARE HERE
    ├── README.md                       # This file
    ├── ARCHITECTURE_AUTH.md            # Auth module details
    ├── ARCHITECTURE_CV.md              # CV module details
    └── ARCHITECTURE_MATCH.md           # Match module details
```

---

## 🔄 Data Flow Examples

### Scenario 1: User registers and uploads CV

```
1. User calls: POST /api/auth/register
   ↓ (ARCHITECTURE_AUTH.md - Section 1)
   Create User → PostgreSQL
   
2. User calls: POST /api/auth/login
   ↓ (ARCHITECTURE_AUTH.md - Section 2)
   Validate credentials → Return JWT tokens
   
3. User calls: POST /api/cvs/upload
   ↓ (ARCHITECTURE_CV.md - Section 1-2)
   Save file → Parse text → Chunk text
   ↓
   Embed chunks (Sentence-Transformers)
   ↓
   Upsert to Qdrant → Save metadata to PostgreSQL
   
4. Database state:
   - PostgreSQL: users, files, file_chunks records
   - Qdrant: points with vectors + file_id metadata
```

### Scenario 2: User finds matching jobs

```
1. User has CV already uploaded (status=embedded)

2. User calls: GET /api/match/jobs/{cv_id}
   ↓ (ARCHITECTURE_MATCH.md - Section 2)
   Fetch all CV chunks from PostgreSQL
   ↓
   Retrieve vectors from Qdrant
   ↓
   Average pooling → 1 CV vector
   ↓
   Search similar jobs (Qdrant)
   ↓
   Fetch job details from PostgreSQL
   ↓
   Return top 20 jobs sorted by score

3. Results: List of jobs ranked by match score
```

### Scenario 3: User checks CV against specific job

```
1. User has JD text (copy-pasted from job site)

2. User calls: POST /api/match/cv-vs-jd
   ↓ (ARCHITECTURE_MATCH.md - Section 1)
   Embed JD text (Sentence-Transformers)
   ↓
   Search CV chunks in Qdrant
   ↓
   Calculate average score
   ↓
   Return matching CV chunks + overall score

3. Results: Overall match score + top matching parts of CV
```

---

## 🛠️ Technology Stack by Module

### Auth Module
- **Framework**: FastAPI
- **Auth**: Python-Jose (JWT), PassLib (password hashing)
- **Database**: SQLAlchemy + asyncpg + PostgreSQL
- **Session**: Refresh tokens (stored in SQL)

### CV Module
- **File Parsing**:
  - PDF: PyPDF2 + PyMuPDF (fallback on scanned)
  - DOCX: python-docx
  - OCR: Tesseract + pytesseract + Pillow
- **Text Processing**: Custom chunking + cleaning
- **Vectorization**: Sentence-Transformers (1024-dim)
- **Storage**: File disk + PostgreSQL metadata + Qdrant vectors

### Match Module
- **Similarity Computation**: Cosine similarity (Qdrant built-in)
- **Vector Search**: Qdrant client (async)
- **Aggregation**: Average pooling (custom code)
- **Result Building**: PostgreSQL queries + Qdrant scores

---

## 📊 Database Schema

See individual architecture docs for detailed schemas:
- **Auth.md** - `users`, `refresh_tokens` tables
- **CV.md** - `files`, `file_chunks` tables
- **Match.md** - (Uses existing tables + Qdrant collections)

---

## 🔍 Understanding Key Concepts

### JWT Access Token
- Short-lived (30 min)
- Stateless (no server lookup needed)
- Payload: `{sub: user_id, exp: timestamp, iat: timestamp}`
- Used for protecting API endpoints

### Refresh Token
- Long-lived (7 days)
- Stateful (hashed in DB, can be revoked)
- Used to get new access tokens
- Supports multi-device sessions (separate tokens per device)

### Text Embedding
- Transform text → numeric vector (1024 dimensions)
- Similar text → similar vectors
- Model: BAAI/bge-m3 (multilingual, 1K dim)
- Enables semantic similarity (not keyword matching)

### Qdrant Vector Database
- Fast nearest-neighbor search
- Supports filtering by payload fields
- Two collections: "cvs" (chunks) + "jobs" (full jobs)
- Cosine similarity metric (0-1 range)

### Average Pooling
- CV = 15-20 chunks
- Each chunk = 1024-dim vector
- Average = (sum of all chunk vectors) / num_chunks
- Result = 1 vector representing whole CV

---

## 🚀 Quick Links

| Need | File | Section |
|------|------|---------|
| Add login feature | [ARCHITECTURE_AUTH.md](./ARCHITECTURE_AUTH.md) | Section 2 |
| Add new parser | [ARCHITECTURE_CV.md](./ARCHITECTURE_CV.md) | Section 3 |
| Improve matching algorithm | [ARCHITECTURE_MATCH.md](./ARCHITECTURE_MATCH.md) | Section 2-3 |
| Understand token flow | [ARCHITECTURE_AUTH.md](./ARCHITECTURE_AUTH.md) | Section 2-3 |
| Add new embedding model | [ARCHITECTURE_CV.md](./ARCHITECTURE_CV.md) | Section 2 |
| Troubleshoot CV parsing | [ARCHITECTURE_CV.md](./ARCHITECTURE_CV.md) | Section 3 |

---

## 🔗 Related Documentation

- [Main README](../README.md) - Setup and running project
- [Backend Source Code](../backend/app) - Implementation
- [Alembic Migrations](../backend/alembic) - Database versions

---

## 📞 Questions?

Refer to specific sections in the architecture documents above for:
- Detailed flow diagrams
- Database schemas
- cURL command examples
- Troubleshooting guides
- Implementation files

---

**Last updated**: 2026-04-10  
**Version**: 1.0
