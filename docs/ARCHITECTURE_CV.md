# 📄 Luồng xử lý CV (CV Processing Pipeline)

## Tổng quan

Module CV quản lý:
- 📤 **Upload** file CV (PDF, DOCX)
- 🔍 **Parse** text từ file
- ✂️ **Chunk** text thành các đoạn nhỏ
- 🧠 **Embed** text thành vectors
- 📊 **Danh sách** CV của user
- 🔎 **Chi tiết** 1 CV với chunks

---

## 1️⃣ Upload CV

### Endpoint
```
POST /api/cvs/upload
Header: Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file: <binary PDF/DOCX>
```

### Response (201 Created)
```json
{
  "id": "uuid",
  "original_name": "CV_NguyenVanA.pdf",
  "stored_name": "a1b2c3d4e5f6.pdf",
  "mime_type": "application/pdf",
  "size": 245678,
  "status": "embedded",
  "chunk_count": 15,
  "created_at": "2026-04-10T10:00:00Z"
}
```

### Luồng xử lý chi tiết

```
📥 INPUT: User upload file
           ↓
1️⃣ VALIDATE EXTENSION
   ├─ Get extension: Path(filename).suffix.lower()
   ├─ Check: ext in {".pdf", ".docx", ".doc"}
   ├─ Hợp lệ → Tiếp tục
   └─ Không → HTTP 415: "Chi chap nhan file .pdf hoac .docx"
           ↓
2️⃣ VALIDATE FILE SIZE
   ├─ Read all bytes: await file.read()
   ├─ Check: len(file_bytes) <= 10 MB
   ├─ Hợp lệ → Tiếp tục
   └─ Vượt quá → HTTP 413: "File qua lon. Toi da 10 MB"
           ↓
3️⃣ SAVE FILE TO DISK
   ├─ Generate unique name: f"{uuid.uuid4().hex}{ext}"
   │  Ví dụ: a1b2c3d4e5f6.pdf
   ├─ Write bytes to: uploads/cvs/{stored_name}
   └─ Save file_path for later access
           ↓
4️⃣ CREATE FILE RECORD
   ├─ Insert into files table:
   │  {
   │    id: uuid.uuid4(),
   │    user_id: current_user.id,
   │    original_name: "CV_NguyenVanA.pdf",
   │    stored_name: "a1b2c3d4e5f6.pdf",
   │    file_path: "/absolute/path/uploads/cvs/a1b2c3d4e5f6.pdf",
   │    mime_type: "application/pdf",
   │    size: 245678,
   │    status: "parsing",          // Trạng thái: parsing → embedded → failed
   │  }
   ├─ db.flush() để lấy id
   └─ Continue processing
           ↓
5️⃣ PARSE TEXT
   ├─ Initialize CVParser (orchestrator)
   ├─ CVParser.parse(file_path) → raw_text
   │
   │  Parsing strategy:
   │  • PDF file → Try PDFParser (pypdf) first
   │    - Nếu extract được text dài hơn 30 ký tự → OK
   │    - Nếu text < 30 ký tự → Fallback OCR (scanned PDF)
   │  • DOCX file → DOCXParser (python-docx) directly
   │
   └─ raw_text = Extracted full text from CV
           ↓
6️⃣ CLEAN TEXT
   ├─ Call clean_text(raw_text)
   │  Removes:
   │  - Extra whitespace
   │  - Special characters
   │  - Normalize unicode
   └─ cleaned_text saved
           ↓
7️⃣ CHUNK TEXT
   ├─ Call chunk_text(cleaned_text, chunk_size=300, overlap=50)
   │
   │  Word-based chunking with sliding window:
   │  • Split by words (not characters)
   │  • ~300 words per chunk
   │  • 50-word overlap between chunks
   │  • Preserve context between chunks
   │
   ├─ Returns: list[dict] with:
   │  {
   │    "content": "word1 word2 word3...",
   │    "chunk_index": 0,
   │    "token_count": 45
   │  }
   │
   └─ chunks_data = [chunk1, chunk2, ...]
           ↓
8️⃣ SAVE CHUNKS TO DB
   ├─ For each chunk in chunks_data:
   │  INSERT into file_chunks {
   │    file_id: db_file.id,
   │    chunk_index: 0, 1, 2, ...
   │    content: "cleaned chunk text",
   │    status: "embedding",
   │    metadata_json: {"token_count": 45}
   │  }
   │  (Note: qdrant_point_id is NULL at this stage)
   │
   └─ Each chunk gets its own row
           ↓
9️⃣ EMBED CHUNKS
   ├─ Call embed_file(file_id, db)
   │  (Betas embedding service - see section 2️⃣ below)
   │  • Load Sentence-Transformers model (BAAI/bge-m3)
   │  • Batch encode all chunks → numpy vectors
   │  • Upsert vectors into Qdrant
   │  • Save qdrant_point_id back to DB
   │
   └─ All chunks get vector embeddings
           ✓
🔟 UPDATE FILE STATUS
   ├─ Update db_file:
   │  status = "embedded"
   │  (now ready for similarity search)
   │
   └─ Commit to DB
           ↓
1️⃣1️⃣ RETURN RESPONSE
   └─ FileResponse with:
      - id, original_name, stored_name
      - mime_type, size, status
      - chunk_count (number of chunks created)
```

### Error Handling

```
Try parsing:
├─ ParseError caught
│  ├─ Update status = "failed"
│  ├─ Log error with details
│  └─ HTTP 422: Return error details to client
│
└─ Unexpected exception
   ├─ Update status = "failed"
   ├─ Log full traceback
   └─ HTTP 500: "UNEXPECTED_ERROR"
```

---

## 2️⃣ Embedding Service

### Hàm: `embed_file(file_id, db)`

```
📥 INPUT: file_id (UUID of CV file)
          db (AsyncSession)
          ↓
1️⃣ FETCH CHUNKS
   ├─ SELECT * FROM file_chunks
   │  WHERE file_id = ?
   │    AND qdrant_point_id IS NULL  // Only unembed chunks
   │    ORDER BY chunk_index
   │
   ├─ If no chunks → Return 0
   └─ rows = [chunk1, chunk2, ...]
           ↓
2️⃣ LOAD MODEL
   ├─ Model: Sentence-Transformers (BAAI/bge-m3)
   ├─ Size: 1024 dimension vectors
   ├─ Language: Multilingual (English + Vietnamese)
   ├─ Lazy load: cache model in memory
   │  (primeiro call load từ huggingface, calls later reuse)
   │
   └─ model = SentenceTransformer("BAAI/bge-m3")
           ↓
3️⃣ BATCH ENCODE
   ├─ Extract texts: [chunk.content for chunk in rows]
   ├─ Encode all at once:
   │  vectors = model.encode(
   │    texts,
   │    batch_size=32,
   │    show_progress_bar=False
   │  )
   │
   ├─ Returns: numpy array shape (len(texts), 1024)
   │  where 1024 is vector dim
   │
   └─ Fast because batch processing (vectorized)
           ↓
4️⃣ UPSERT TO QDRANT
   ├─ Prepare point structures:
   │  for chunk, vector in zip(rows, vectors):
   │    point = PointStruct(
   │      id = uuid.uuid4(),  // Point ID in Qdrant
   │      vector = vector.tolist(),  // [0.1, 0.2, ..., 0.15]
   │      payload = {          // Metadata for filtering
   │        "pg_job_id": chunk.file_id,
   │        "chunk_db_id": chunk.id,
   │        "chunk_index": chunk.chunk_index,
   │        "content": chunk.content,  // For returning in results
   │      }
   │    )
   │
   ├─ Batch upload all:
   │  client.upsert(
   │    collection_name="cvs",
   │    points=[point1, point2, ...]
   │  )
   │
   └─ point_ids returned from Qdrant
           ↓
5️⃣ UPDATE DB RECORDS
   ├─ For each (chunk, point_id) pair:
   │  chunk.qdrant_point_id = point_id
   │  chunk.embedded_at = now()
   │  chunk.embedding_model = "BAAI/bge-m3"
   │
   ├─ Commit to PostgreSQL
   └─ Now each chunk has Qdrant reference
           ✓
6️⃣ RETURN COUNT
   └─ Return number of embedded chunks
```

### Qdrant Collection Schema

**Collection: `cvs`**
```json
{
  "collection_name": "cvs",
  "vectors_config": {
    "size": 1024,
    "distance": "cosine"  // Similarity metric
  }
}
```

**Point Structure:**
```json
{
  "id": "00112233445566778899aabb",
  "vector": [0.1, 0.2, ..., 0.15],  // 1024 dimensions
  "payload": {
    "pg_file_id": "uuid-of-cv-file",
    "chunk_db_id": "uuid-of-chunk-in-postgres",
    "chunk_index": 0,
    "content": "The actual text of this chunk..."
  }
}
```

---

## 3️⃣ Parsing Strategies

### PDF Parsing (2-step strategy)

```
PDF File
    ↓
1️⃣ Try PDFParser (pypdf)
    ├─ Extract text using pypdf library
    ├─ Fast, pure Python
    │
    ├─ If parsing error → Fallback OCR
    │
    └─ If OK → Check length:
       └─ If len(text) >= 30 chars → RETURN text (text-based PDF)
       └─ If len(text) < 30 chars → FALLBACK OCR (likely scanned)
    ↓
2️⃣ If fallback → OCRParser (PyMuPDF + Tesseract)
    ├─ PyMuPDF: Extract images from PDF pages
    ├─ Tesseract: OCR each image → text
    ├─ Combine all → full text
    │
    └─ Return OCRed text
    
Result: Full text (either native extraction or OCR)
```

### DOCX Parsing

```
DOCX File (Word document)
    ↓
DOCXParser (python-docx)
    ├─ Extract text from all paragraphs
    ├─ Extract from tables
    ├─ Preserve structure
    │
    └─ Return combined text
    
Result: Full text from document
```

---

## 4️⃣ Text Chunking Strategy

### Sliding Window with Overlap

```
Original text:
"word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 ..."
   |←─── chunk_size = 300 words ───→|
   chunk 0: word1...word300
   
                |←── overlap = 50 words ───→|
                chunk 1: word251...word550
                
                              |←── ... ─→|
                              chunk 2: ...

Advantages:
- Word-based (not character-based) → preserves semantics
- Overlap preserves context between chunks
- Each chunk ~300 words (~3-5 sentences usually)
```

### Output Format

```python
[
  {
    "content": "word1 word2 ... word300",
    "chunk_index": 0,
    "token_count": 298
  },
  {
    "content": "word251 word252 ... word550",
    "chunk_index": 1,
    "token_count": 300
  },
  # ... more chunks
]
```

---

## 5️⃣ List CVs

### Endpoint
```
GET /api/cvs
Header: Authorization: Bearer <access_token>
```

### Response (200 OK)
```json
{
  "files": [
    {
      "id": "uuid1",
      "original_name": "CV_NguyenVanA.pdf",
      "stored_name": "a1b2c3d4e5f6.pdf",
      "status": "embedded",
      "chunk_count": 15,
      "created_at": "2026-04-10T10:00:00Z"
    },
    {
      "id": "uuid2",
      "original_name": "CV_Latest.docx",
      "stored_name": "x9y8z7w6v5u4.docx",
      "status": "embedded",
      "chunk_count": 22,
      "created_at": "2026-04-10T11:00:00Z"
    }
  ],
  "total": 2
}
```

### Luồng xử lý
```
1. Get current_user from JWT token
2. SELECT * FROM files 
   WHERE user_id = current_user.id
   ORDER BY created_at DESC
3. For each file:
   - Count chunks: SELECT COUNT(*) FROM file_chunks WHERE file_id = ?
   - Return with chunk_count
4. Return FileListResponse
```

---

## 6️⃣ Get CV Chi tiết

### Endpoint
```
GET /api/cvs/{cv_id}
Header: Authorization: Bearer <access_token>
```

### Response (200 OK)
```json
{
  "id": "uuid",
  "original_name": "CV_NguyenVanA.pdf",
  "stored_name": "a1b2c3d4e5f6.pdf",
  "mime_type": "application/pdf",
  "size": 245678,
  "status": "embedded",
  "created_at": "2026-04-10T10:00:00Z",
  "chunks": [
    {
      "chunk_index": 0,
      "content": "Personal Information... lorem ipsum...",
      "embedded_at": "2026-04-10T10:05:00Z",
      "embedded_model": "BAAI/bge-m3"
    },
    {
      "chunk_index": 1,
      "content": "Experience... lorem ipsum...",
      "embedded_at": "2026-04-10T10:05:00Z",
      "embedded_model": "BAAI/bge-m3"
    }
    # ... more chunks
  ]
}
```

### Luồng xử lý
```
1. Get current_user
2. Verify CV belongs to user:
   SELECT * FROM files 
   WHERE id = cv_id AND user_id = current_user.id
3. If not found → 404
4. SELECT * FROM file_chunks 
   WHERE file_id = cv_id
   ORDER BY chunk_index
5. Return with all chunks
```

---

## 📊 Database Schema

### files table
```sql
CREATE TABLE files (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  original_name VARCHAR NOT NULL,
  stored_name VARCHAR NOT NULL,
  file_path VARCHAR NOT NULL,
  mime_type VARCHAR,
  size INT,
  status VARCHAR DEFAULT 'parsing',  -- 'parsing' | 'embedded' | 'failed'
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_files_user_id ON files(user_id);
```

### file_chunks table
```sql
CREATE TABLE file_chunks (
  id UUID PRIMARY KEY,
  file_id UUID NOT NULL REFERENCES files(id),
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  qdrant_point_id UUID,              -- Reference to Qdrant point
  embedded_at TIMESTAMP,
  embedding_model VARCHAR,            -- e.g., "BAAI/bge-m3"
  metadata_json JSONB,               -- {"token_count": 298}
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_file_chunks_file_id ON file_chunks(file_id);
CREATE INDEX idx_file_chunks_qdrant_point_id ON file_chunks(qdrant_point_id);
```

---

## 🔄 File Processing Workflow Diagram

```
User Upload CV
    ↓
Validate Extension/Size
    ↓ (On error: HTTP 4xx)
Save to Disk
    ↓
Create File Record (status=parsing)
    ↓
Parse Text
├─ PDF: PDFParser → fallback OCR if needed
└─ DOCX: DOCXParser
    ↓ (On error: status=failed, HTTP 422)
Clean Text
    ↓
Chunk Text (overlap=50 words)
    ↓ (On error: status=failed, HTTP 500)
Create FileChunk records (qdrant_point_id=NULL)
    ↓
Embed Chunks
├─ Load Sentence-Transformers model
├─ Batch encode to vectors (1024-dim)
└─ Upsert to Qdrant
    ↓
Update FileChunk (add qdrant_point_id)
    ↓
Update File (status=embedded)
    ↓
Return FileResponse (201 Created)
    ↓
Ready for Search/Matching!
```

---

## 🧪 Example cURL Commands

### Upload PDF CV
```bash
export TOKEN="<access_token>"
curl -X POST "http://localhost:8000/api/cvs/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./my_cv.pdf"

# Response: File uploaded, chunks created, vectors embedded
```

### Upload DOCX CV
```bash
curl -X POST "http://localhost:8000/api/cvs/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./cv.docx"
```

### List My CVs
```bash
curl -X GET "http://localhost:8000/api/cvs" \
  -H "Authorization: Bearer $TOKEN"
```

### Get CV with Chunks
```bash
CV_ID="<uuid_from_list>"
curl -X GET "http://localhost:8000/api/cvs/$CV_ID" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📝 Implementation Files

- **Router**: [app/routers/cv.py](../backend/app/routers/cv.py)
- **CV Parser Orchestrator**: [app/services/cv_parser.py](../backend/app/services/cv_parser.py)
- **Embedding Service**: [app/services/embedding_service.py](../backend/app/services/embedding_service.py)
- **PDF Parser**: [app/parsers/pdf_parser.py](../backend/app/parsers/pdf_parser.py)
- **DOCX Parser**: [app/parsers/docx_parser.py](../backend/app/parsers/docx_parser.py)
- **OCR Parser**: [app/parsers/ocr_parser.py](../backend/app/parsers/ocr_parser.py)
- **Text Cleaner**: [app/parsers/text_cleaner.py](../backend/app/parsers/text_cleaner.py)
- **Qdrant Service**: [app/services/qdrant_services.py](../backend/app/services/qdrant_services.py)
