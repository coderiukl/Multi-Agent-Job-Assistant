from fastapi import FastAPI
from app.routers import auth, cv, match
from app.services.qdrant_services import ensure_collection


app = FastAPI(title="Multi-Agent Job Assistant Systems")

app.include_router(auth.router)
app.include_router(cv.router)
app.include_router(match.router)

@app.on_event("startup")
async def startup():
    return await ensure_collection()

@app.get("/health")
async def health():
    return {"status": "ok"}

