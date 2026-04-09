# 🎯 Luồng so khớp việc làm (Job Matching Pipeline)

## Tổng quan

Module match quản lý:
- 📊 **So khớp CV vs JD** - So sánh 1 CV với 1 mô tả công việc
- 🔍 **Tìm jobs phù hợp** - Tìm danh sách jobs phù hợp nhất với CV
- 🧠 **Semantic search** - Dùng embeddings + Qdrant vector search

---

## 1️⃣ So khớp CV vs JD (Match CV vs Job Description)

### Endpoint
```
POST /api/match/cv-vs-jd
Content-Type: application/json

{
  "cv_file_id": "uuid-of-cv-file",
  "jd_text": "We are looking for a Python developer with 3+ years experience... Django, FastAPI, PostgreSQL...",
  "top_k": 10
}
```

### Response (200 OK)
```json
{
  "score": 0.78543,
  "matching_chunks": [
    {
      "content": "3 years experience in Python development... Django, FastAPI, PostgreSQL",
      "score": 0.89234,
      "chunk_index": 2
    },
    {
      "content": "Backend development with modern frameworks",
      "score": 0.82134,
      "chunk_index": 5
    },
    {
      "content": "Database design and optimization",
      "score": 0.71456,
      "chunk_index": 8
    }
  ]
}
```

### Luồng xử lý chi tiết

```
📥 INPUT: cv_file_id + jd_text + top_k
          ↓
1️⃣ VALIDATE INPUT
   ├─ Check jd_text not empty
   ├─ If empty → HTTP 422: "jd_text không được để trống"
   └─ Continue
           ↓
2️⃣ EMBED JD TEXT
   ├─ Call _embed_text(jd_text)
   │  ├─ Load model: Sentence-Transformers
   │  ├─ Encode JD using same model as CV chunks
   │  │  (Must be same model for meaningful comparison!)
   │  └─ Returns: vector of 1024 dimensions
   │
   ├─ jd_vector = [0.1, -0.2, 0.15, ..., 0.05]  (1024 dims)
   └─ Ready for search
           ↓
3️⃣ SEMANTIC SEARCH IN QDRANT
   ├─ Call search_similar(
   │    vector=jd_vector,
   │    top_k=10,
   │    file_id_filter=cv_file_id  // Only search CV's chunks
   │  )
   │
   ├─ Qdrant returns top 10 (top_k) closest chunks:
   │  hits = [
   │    {
   │      "id": "qdrant-point-id",
   │      "score": 0.89234,         // Cosine similarity: 0-1
   │      "content": "text of chunk",
   │      "chunk_index": 2
   │    },
   │    {
   │      "id": "...",
   │      "score": 0.82134,
   │      "content": "...",
   │      "chunk_index": 5
   │    },
   │    # ... more hits
   │  ]
   │
   └─ Already sorted by similarity (best first)
           ↓
4️⃣ CALCULATE OVERALL SCORE
   ├─ If no hits found:
   │  └─ overall_score = 0.0
   │
   └─ If hits found:
      ├─ average_score = sum(h["score"] for h in hits) / len(hits)
      │  Example: (0.89 + 0.82 + 0.71 + ...) / 10 = 0.78543
      │
      └─ overall_score = average_score (rounded to 5 decimals)
           ✓
5️⃣ BUILD RESPONSE
   ├─ CvVsJdResponse {
   │    "score": 0.78543,
   │    "matching_chunks": [
   │      {
   │        "content": "chunk text",
   │        "score": 0.89234,
   │        "chunk_index": 2
   │      },
   │      ...
   │    ]
   │  }
   │
   └─ Return JSON response (200 OK)
```

### Semantic Similarity Explained

```
CV Chunk:     "3 years Python, Django, PostgreSQL"
              ↓ [encode]
              [0.1, -0.2, 0.15, ..., 0.05]  (1024 dims)
              
JD Text:      "Looking for 3+ years Python developer"
              ↓ [encode with SAME model]
              [0.12, -0.18, 0.16, ..., 0.06]  (1024 dims)
              
Cosine Similarity:
    score = dot_product(vec1, vec2) / (||vec1|| * ||vec2||)
          = 0.89234  (out of 0-1)
          
Interpretation:
- score = 1.0     → Identical meaning
- score = 0.8-1.0 → Very similar
- score = 0.5-0.8 → Somewhat related
- score = 0-0.5   → Not related
- score = 0.0     → Completely different
```

### Why This Works

✅ **Semantic matching** (not keyword matching)
- CV chunk: "3 years developing backend systems"
- JD: "3+ years backend software engineer experience"
- Keyword match: 0 matches (different words)
- Semantic match: 0.92 (same meaning!)

✅ **Multi-language support**
- Model trained on multilingual data
- Works with English, Vietnamese, etc.
- Score meaningful across languages

✅ **Context-aware**
- Whole sentences (not words)
- Preserves context thanks to chunking overlap
- Catches nuanced meanings

---

## 2️⃣ Tìm Jobs phù hợp (Find Matching Jobs)

### Endpoint
```
GET /api/match/jobs/{cv_file_id}?top_k=20
Header: Authorization: Bearer <access_token>
```

### Response (200 OK)
```json
[
  {
    "id": "uuid-of-job",
    "title": "Python Backend Developer",
    "company": "Tech Company ABC",
    "location": "Ho Chi Minh City",
    "country": "Vietnam",
    "category": "IT - Software",
    "contract_type": "Permanent",
    "salary_min": 20000000,
    "salary_max": 35000000,
    "salary_avg": 27500000,
    "technical_skills": "Python, Django, PostgreSQL, Docker",
    "experience_required": "3-5 years",
    "url": "https://example.com/job/123",
    "score": 0.87654
  },
  {
    "id": "uuid-of-job-2",
    "title": "Full-stack Web Developer",
    "company": "StartUp XYZ",
    "location": "Da Nang",
    "country": "Vietnam",
    "category": "IT - Software",
    "contract_type": "Contract",
    "salary_min": 15000000,
    "salary_max": 25000000,
    "salary_avg": 20000000,
    "technical_skills": "JavaScript, React, Node.js",
    "experience_required": "2-3 years",
    "url": "https://example.com/job/124",
    "score": 0.75432
  }
  # ... more jobs, sorted by score descending
]
```

### Luồng xử lý chi tiết

```
📥 INPUT: cv_file_id + top_k parameter
          ↓
1️⃣ VERIFY CV EXISTS & IS EMBEDDED
   ├─ Fetch File record:
   │  SELECT * FROM files 
   │  WHERE id = cv_file_id 
   │  AND user_id = current_user.id
   │
   ├─ Not found → HTTP 404
   ├─ Status != "embedded" → Not ready, HTTP 422
   └─ Found & embedded → Continue
           ↓
2️⃣ GET CV REPRESENTATIVE VECTOR
   ├─ Call get_cv_representative_vector(cv_file_id, db)
   │  (This function computes average of all CV chunks)
   │
   │  Steps inside:
   │  ├─ SELECT * FROM file_chunks
   │  │  WHERE file_id = cv_file_id
   │  │  AND qdrant_point_id IS NOT NULL
   │  │  ORDER BY chunk_index
   │  │
   │  ├─ If no chunks → Return None (not embedded yet)
   │  │
   │  ├─ Get Qdrant point IDs from chunks
   │  │
   │  ├─ Retrieve all point vectors from Qdrant:
   │  │  For each point_id:
   │  │    point.vector = [0.1, -0.2, ..., 0.05]  (1024 dims)
   │  │
   │  ├─ Average pooling (dimension-wise average):
   │  │  avg_vector[i] = sum(v[i] for v in all_vectors) / len(vectors)
   │  │
   │  │  Example with 3 chunks:
   │  │  chunk_vec_1 = [0.10, -0.20, 0.15, ...]
   │  │  chunk_vec_2 = [0.12, -0.18, 0.16, ...]
   │  │  chunk_vec_3 = [0.08, -0.22, 0.14, ...]
   │  │  avg_vector  = [0.10, -0.20, 0.15, ...]  (averaged)
   │  │
   │  └─ cv_vector = representative vector for entire CV
   │
   └─ cv_vector ready for job search
           ↓
3️⃣ SEARCH SIMILAR JOBS IN QDRANT
   ├─ Call search_similar(
   │    vector=cv_vector,
   │    top_k=20,
   │    file_id_filter=None,  // Search in JOBS collection, not CV
   │    search_type="jobs"
   │  )
   │
   ├─ Qdrant searches job vectors:
   │  jobs_hits = [
   │    {
   │      "pg_job_id": "uuid-of-job-1",
   │      "title": "Python Backend Developer",
   │      "company": "Tech Company ABC",
   │      "location": "Ho Chi Minh City",
   │      "score": 0.87654,  // Cosine similarity to CV
   │      # ... other job fields
   │    },
   │    {
   │      "pg_job_id": "uuid-of-job-2",
   │      "title": "Full-stack Web Developer",
   │      "score": 0.75432,
   │      # ...
   │    },
   │    # ... top 20 jobs
   │  ]
   │
   └─ Already sorted by score (best matches first)
           ↓
4️⃣ FETCH JOB DETAILS FROM DB
   ├─ For each job in hits:
   │  SELECT * FROM jobs WHERE id = job_id
   │  (Get full job details from PostgreSQL)
   │
   └─ Combine with Qdrant score
           ↓
5️⃣ BUILD RESPONSE
   ├─ List[JobMatchResult] {
   │    id, title, company, location, ...
   │    technical_skills, experience_required, ...
   │    score  (similarity to CV)
   │  }
   │
   └─ Return JSON array (200 OK)
           ✓
   
   Otherwise:
   ├─ If no jobs found:
   │  HTTP 404: "Không tìm thấy job phù hợp hoặc CV chưa được embed"
   └─ If CV not embedded yet:
      HTTP 422: "CV chưa sẵn sàng (status != embedded)"
```

### How CV is Represented

```
Method: Average pooling of all chunks

Input: All chunks of CV already embedded as vectors

CV = [Chunk1_vec, Chunk2_vec, Chunk3_vec, ..., ChunkN_vec]

CV_Vector = (Chunk1_vec + Chunk2_vec + ... + ChunkN_vec) / N

Result: Single 1024-dim vector representing entire CV

Why this works:
• Captures overall profile (all skills, experience, education)
• Robust to minor variations (not too sensitive to wording)
• Computationally efficient (one vector per CV)
• Can be compared with job vectors using cosine similarity
```

---

## 3️⃣ Search Service Implementation

### Function: `search_similar(vector, top_k, file_id_filter)`

```python
async def search_similar(
    vector: list[float],
    top_k: int = 10,
    file_id_filter: str = None,  # If set, only search this file
) -> list[dict]:
    """
    Search in Qdrant using vector similarity.
    """
    client = get_qdrant_client()
    
    # Build filter if file_id provided
    if file_id_filter:
        filter = Filter(
            must=[
                FieldCondition(
                    key="file_id",
                    match=MatchValue(value=file_id_filter)
                )
            ]
        )
    else:
        filter = None
    
    # Search Qdrant
    results = client.search(
        collection_name=COLLECTION_NAME,  # "cvs" or "jobs"
        query_vector=vector,
        query_filter=filter,
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )
    
    # Transform to list[dict]
    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload  # Include all metadata
        }
        for r in results
    ]
```

### Qdrant Collections

**Collection 1: `cvs` (CV chunks)**
```json
{
  "name": "cvs",
  "vectors": {
    "size": 1024,
    "distance": "cosine"
  },
  "points": [
    {
      "id": "qdrant-point-id",
      "vector": [0.1, -0.2, ..., 0.05],  // 1024 dims
      "payload": {
        "pg_file_id": "uuid-of-cv-file",
        "chunk_db_id": "uuid-of-chunk-row",
        "chunk_index": 0,
        "content": "Personal Information... CV chunk text..."
      }
    },
    # ... more CV chunk points
  ]
}
```

**Collection 2: `jobs` (Job descriptions)**
```json
{
  "name": "jobs",
  "vectors": {
    "size": 1024,
    "distance": "cosine"
  },
  "points": [
    {
      "id": "qdrant-point-id",
      "vector": [0.2, -0.1, ..., 0.08],  // 1024 dims
      "payload": {
        "pg_job_id": "uuid-of-job",
        "title": "Python Backend Developer",
        "location": "Ho Chi Minh City",
        "country": "Vietnam",
        "category": "IT - Software",
        "salary_min": 20000000,
        "salary_max": 35000000,
        "salary_avg": 27500000,
        "contract_type": "Permanent",
        "experience_required": "3-5 years",
        "url": "https://example.com/job/123",
        # ... all job fields
      }
    },
    # ... more job points
  ]
}
```

---

## 🔄 Complete Workflow Diagram

### Scenario: User uploads CV and wants to find jobs

```
┌─────────────────────────────────────────────┐
│ Step 1: User uploads CV                     │
│ POST /api/cvs/upload                        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ CV Processing                               │
│ - Parse text                                │
│ - Chunk into ~15-20 pieces                 │
│ - Embed each chunk (1024-dim vector)       │
│ - Store in Qdrant (cvs collection)         │
└────────────────┬────────────────────────────┘
                 │
                 ▼
        File status: "embedded"
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Step 2: User wants matching jobs            │
│ GET /api/match/jobs/{cv_file_id}           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Get CV Representative Vector               │
│ - Average all CV chunk vectors             │
│ - Result: 1 vector representing entire CV  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Qdrant Semantic Search                      │
│ - Query: CV_vector                          │
│ - Search in: jobs collection               │
│ - Top K: 20 most similar jobs              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Score + Return Results                      │
│ Each job with similarity score (0-1)       │
│ Sorted by score (best first)               │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         User sees matching jobs!
```

### Scenario: User wants to match CV against 1 specific job

```
┌─────────────────────────────────────────────┐
│ Step: User has CV + JD text                 │
│ POST /api/match/cv-vs-jd                   │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Embed JD Text                               │
│ - Same embedding model as CV chunks        │
│ - Result: 1 vector (1024 dims)             │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Qdrant Semantic Search                      │
│ - Query: JD_vector                          │
│ - Search in: cv chunks (file_id_filter)    │
│ - Top K: 10 most relevant CV chunks        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Score  Calculation                          │
│ - Overall: Average of all chunk scores     │
│ - Return: Overall score + matching chunks  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
User sees: Overall match score + matching parts
```

---

## 📊 Scoring Examples

### Example 1: CV vs Specific JD

```
CV has chunks:
├─ Chunk 1: "3 years Python development"      [embedded]
├─ Chunk 2: "Firebase, PostgreSQL databases"  [embedded]
├─ Chunk 3: "Team lead for 2-person agile"    [embedded]
└─ Chunk 4: "Full-stack web development"      [embedded]

JD text: "Looking for 3+ years Python expert with database skills" 
         [embedded]

Qdrant search top_k=3:
├─ Match 1: Chunk 1 ← score: 0.94 (very similar)
├─ Match 2: Chunk 2 ← score: 0.87 (similar: "database")
└─ Match 3: Chunk 4 ← score: 0.72 (somewhat related)

Overall score = (0.94 + 0.87 + 0.72) / 3 = 0.84
```

### Example 2: CV Search for Jobs

```
CV Average Vector: [0.05, -0.15, 0.12, ..., -0.03]  (averaged over 15 chunks)

Qdrant search in jobs collection top_k=3:

Job 1: "Python Backend Developer"
  - Vector: [0.07, -0.14, 0.13, ...]
  - Cosine sim: 0.91 ← MATCH! Similar skills

Job 2: "Full-stack JavaScript Developer"
  - Vector: [0.20, -0.30, 0.05, ...]
  - Cosine sim: 0.58 ← NO MATCH: Different tech stack

Job 3: "Senior Backend Engineer (Python)"
  - Vector: [0.04, -0.16, 0.11, ...]
  - Cosine sim: 0.88 ← MATCH! Very similar

Results returned sorted by score:
1. Job 3 (score: 0.88)
2. Job 1 (score: 0.91)
...
```

---

## 📝 Implementation Files

- **Router**: [app/routers/match.py](../backend/app/routers/match.py)
- **Search Service**: [app/services/search_services.py](../backend/app/services/search_services.py)
- **Qdrant Service**: [app/services/qdrant_services.py](../backend/app/services/qdrant_services.py)
- **Embedding Service**: [app/services/embedding_service.py](../backend/app/services/embedding_service.py)

---

## 🧪 Example cURL Commands

### Match CV vs JD
```bash
export TOKEN="<access_token>"
export CV_ID="<cv_file_id>"

curl -X POST "http://localhost:8000/api/match/cv-vs-jd" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_file_id": "'$CV_ID'",
    "jd_text": "We are looking for a Python developer with 3+ years experiencer, knowledge of Django, FastAPI, PostgreSQL",
    "top_k": 10
  }'
```

### Find Matching Jobs
```bash
export TOKEN="<access_token>"
export CV_ID="<cv_file_id>"

curl -X GET "http://localhost:8000/api/match/jobs/$CV_ID?top_k=20" \
  -H "Authorization: Bearer $TOKEN"

# Returns top 20 jobs sorted by match score
```

---

## 🎓 Key Concepts

### Cosine Similarity
- Measures angle between two vectors
- Range: -1 to 1 (usually 0 to 1 for positive documents)
- 1.0 = identical direction (meaning)
- 0.5 = 60° angle
- 0.0 = perpendicular (unrelated)

### Word Embeddings
- Words/texts transformed to numeric vectors
- Similar texts → similar vectors
- "Python developer" ≈ "Python engineer" (both have similar vector)
- Captures semantic meaning beyond exact keywords

### Batch Embedding
- Encoding multiple pieces of text at once
- 32x faster than encoding one-by-one
- Model can process parallelized operations

### Average Pooling
- Averaging vectors: (v1 + v2 + v3) / 3
- Represents the "center" of multiple vectors
- One CV = one average vector from all chunks
- Enables fast job search (one query instead of many)
