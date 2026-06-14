# app/auth/routes.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/auth/login")
async def login():
    pass

@router.get("/auth/callback")
async def callback():
    pass