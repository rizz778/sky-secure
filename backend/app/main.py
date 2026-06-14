from fastapi import FastAPI

from app.api.assistant_routes import router as assistant_router
from app.auth.routes import router as auth_router

app = FastAPI(title="Zoho Project Assistant")

app.include_router(auth_router)
app.include_router(assistant_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
