# Job Search Agent - Multi-Agent Job Assistant System

Hệ thống hỗ trợ tìm kiếm việc làm tích hợp AI, sử dụng vector embeddings để so khớp CV với các công việc phù hợp.

## 📋 Tổng quan

**Job Search Agent** là một nền tảng giúp:
- 📄 **Parse CV** từ các định dạng khác nhau (PDF, DOCX, Text)
- 🔍 **Tìm kiếm việc làm** dựa trên so khớp semantic (embedding)
- 🤖 **Multi-Agent System** để xây dựng hồ sơ ứng tuyển tối ưu
- 👤 **Quản lý tài khoản** người dùng với xác thực JWT

### Tech Stack

- **Backend**: FastAPI + SQLAlchemy (async)
- **Database**: PostgreSQL (với Alembic migrations)
- **Vector DB**: Qdrant (semantic search)
- **Cache**: Redis
- **AI/ML**: Sentence-Transformers, LangChain, LangGraph
- **OCR**: Tesseract (để trích xuất text từ PDF)
- **Container**: Docker Compose

---

## ✅ Yêu cầu

Trước khi bắt đầu, cần cài đặt:

- **Docker & Docker Compose** (phiên bản mới nhất)
- **Python 3.10+**
- **Tesseract OCR** (nếu chạy local mà không dùng container)
- **Git**

### Cài Tesseract (Tùy chọn - nếu chạy local)

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr libtesseract-dev
```

**Windows:**
Tải installer từ: https://github.com/UB-Mannheim/tesseract/wiki

---

## 🚀 Hướng dẫn Setup

### 1. Clone repository

```bash
git clone https://github.com/coderiukl/Multi-Agent-Job-Assistant.git
cd job-search-agent
```

### 2. Tạo file `.env` trong folder `backend/`

```bash
cd backend
cp .env.example .env  # Nếu có file mẫu, hoặc tạo tay như dưới
```

**Nội dung `.env`:**
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/job_search_agent_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=job_search_agent_db

# JWT Secret (tạo bằng: openssl rand -hex 32)
SECRET_KEY=your-super-secret-key-here-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Qdrant Vector DB
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Redis (tùy chọn)
REDIS_URL=redis://localhost:6379/0
```

### 3. Khởi động Docker Compose

Khởi động tất cả các services (PostgreSQL, Qdrant, Redis):

```bash
docker compose up -d
```

Kiểm tra trạng thái:
```bash
docker compose ps
```

Bạn sẽ thấy 3 containers:
- `cv_postgres` (PostgreSQL port 5433)
- `cv_qdrant` (Qdrant port 6333)
- `cv_redis` (Redis port 6379)

### 4. Cài đặt Python dependencies

```bash
python -m venv venv
source venv/bin/activate  # Trên Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 5. Chạy database migrations

```bash
alembic upgrade head
```

Lệnh này sẽ tạo tất cả các bảng cần thiết trong PostgreSQL.

### 6. (Tùy chọn) Seed dữ liệu việc làm

Nếu có file CSV chứa dữ liệu job:

```bash
python -m scripts.seed_jobs --file data/VietJob.csv
```

Hoặc nếu chỉ muốn test với một số lượng giới hạn:
```bash
python -m scripts.seed_jobs --file data/VietJob.csv --limit 50
```

Script này sẽ:
- Đọc dữ liệu từ CSV
- Inject vào PostgreSQL
- Tạo embeddings và lưu vào Qdrant

### 7. Khởi động API server

```bash
uvicorn app.main:app --reload
```

API sẽ chạy tại: **http://localhost:8000**

Truy cập Swagger UI: **http://localhost:8000/docs**

---

## 📁 Cấu trúc Project

```
backend/
├── app/
│   ├── main.py                 # Entry point của FastAPI
│   ├── core/
│   │   ├── config.py          # Cấu hình từ .env
│   │   ├── dependencies.py    # Database session, auth dependencies
│   │   └── security.py        # JWT token utils
│   ├── db/
│   │   ├── base.py            # SQLAlchemy declarative base
│   │   └── models.py          # Job, User models
│   ├── routers/               # API endpoints
│   │   ├── auth.py            # Login, register
│   │   ├── cv.py              # CV upload, parsing
│   │   └── match.py           # Job matching
│   ├── schemas/               # Pydantic request/response models
│   ├── services/              # Business logic
│   │   ├── embedding_service.py      # Sentence-Transformers
│   │   ├── qdrant_services.py        # Vector DB operations
│   │   ├── search_services.py        # Job search logic
│   │   └── cv_parser.py              # CV parsing orchrestration
│   └── parsers/               # File parsers
│       ├── pdf_parser.py      # PDF extraction
│       ├── docx_parser.py     # DOCX extraction
│       ├── ocr_parser.py      # OCR with Tesseract
│       └── text_cleaner.py    # Text preprocessing
├── alembic/                   # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/              # Migration files
├── scripts/
│   └── seed_jobs.py           # Load jobs from CSV
├── data/
│   └── VietJob.csv            # Sample job data
├── uploads/
│   └── cvs/                   # User uploaded CVs
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Container orchestration
├── alembic.ini               # Alembic config
└── .env                      # Environment variables (create locally)
```

---

## 🔧 Các CLI Commands

### Database

```bash
# Xem trạng thái hiện tại
alembic current

# Xem lịch sử các migrations
alembic history

# Tạo migration mới (sau khi thay đổi models)
alembic revision --autogenerate -m "Mô tả thay đổi"

# Apply migrations
alembic upgrade head

# Rollback 1 migration
alembic downgrade -1
```

### API

```bash
# Chạy với auto-reload trong development
uvicorn app.main:app --reload

# Chạy production (không auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Chạy với Gunicorn (production)
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Data Loading

```bash
# Load jobs từ CSV vào DB
python -m scripts.seed_jobs --file data/VietJob.csv

# Test với 10 jobs
python -m scripts.seed_jobs --file data/VietJob.csv --limit 10
```

---

## 🐳 Docker Commands

```bash
# Khởi động tất cả services
docker compose up -d

# Xem logs
docker compose logs -f postgres        # PostgreSQL logs
docker compose logs -f qdrant          # Qdrant logs
docker compose logs -f redis           # Redis logs

# Dừng tất cả
docker compose down

# Xóa tất cả (bao gồm data)
docker compose down -v

# Rebuild images nếu có thay đổi
docker compose build --no-cache
```

### Connect trực tiếp vào PostgreSQL

```bash
docker exec -it cv_postgres psql -U postgres -d job_search_agent_db

# Sau đó có thể chạy SQL commands:
\dt                           # List tables
SELECT * FROM jobs LIMIT 5;   # Query jobs
```

---

## 🔍 Kiểm tra Health

```bash
# API health check
curl http://localhost:8000/health

# PostgreSQL (từ CLI)
pg_isready -h localhost -p 5433

# Qdrant health (từ browser)
http://localhost:6333/health

# Redis
docker exec cv_redis redis-cli ping
```

---

## 📚 Thêm thông tin

### Environment Variables

| Variable | Mô tả | Mặc định |
|----------|-------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `SECRET_KEY` | JWT signing key | - |
| `QDRANT_HOST` | Qdrant server host | localhost |
| `QDRANT_PORT` | Qdrant server port | 6333 |
| `REDIS_URL` | Redis connection string | - |

### Các Tư liệu tham khảo

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Qdrant Python Client](https://github.com/qdrant/qdrant-client)
- [Sentence-Transformers](https://www.sbert.net/)

---

**Happy coding! 🎉**
