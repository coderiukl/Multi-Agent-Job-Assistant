from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.cv_route import router as cv_router
from routes.jd_route import router as jd_router

from services.qdrant_service import QdrantService
from services.embedding_service import EmbeddingService, SparseEmbeddingService

async def lifespan(app: FastAPI):
    embedding_service = EmbeddingService(
        model_name="BAAI/bge-m3",
        normalize_embeddings=True,
    )

    sparse_embedding_service = SparseEmbeddingService(
        model_name="Qdrant/bm25",
    )

    qdrant_service = QdrantService(
        collection_name="jobs",
        url="http://localhost:6333",
        vector_size=embedding_service.dimension
    )

    app.state.embedding_service = embedding_service
    app.state.sparse_embedding_service = sparse_embedding_service
    app.state.qdrant_service = qdrant_service

    yield

app = FastAPI(
    title="Multi Agent Job Assistant",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cv_router)
app.include_router(jd_router)

@app.get("/")
async def health_check():
    return {"title": "Health Check","status": "ok"}

@app.get("/health/qdrant")
async def qdrant_health():
    collections = app.state.qdrant_service.client.get_collections()

    return {
        "status": "ok",
        "collections": [collection.name for collection in collections.collections]
    }

@app.post("/test-embedding")
async def test_embedding(text: str):
    vector = app.state.embedding_service.embed_text(text)

    return {
        "text": text,
        "dimension": len(vector),
        "vector_preview": vector[:5],
    }