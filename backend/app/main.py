from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assistant_routes import router as assistant_router
from app.api.auth_routes import router as auth_router

app = FastAPI(title="Zoho Project Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(assistant_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
