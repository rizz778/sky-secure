from fastapi import FastAPI

from app.api.zoho_routes import router as zoho_router
from app.auth.routes import router as auth_router

app = FastAPI(title="Zoho Project Assistant")

app.include_router(auth_router)
app.include_router(zoho_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
