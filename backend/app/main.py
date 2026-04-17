from fastapi import FastAPI
from app.routers import auth, cv, match, conversation
from app.services.qdrant_services import ensure_collection
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Multi-Agent Job Assistant Systems")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cv.router)
app.include_router(match.router)
app.include_router(conversation.router)


@app.on_event("startup")
async def startup():
    return await ensure_collection()

@app.get("/health")
async def health():
    return {"status": "ok"}

