import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.login import (
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REDIRECT_URI,
    build_authorization_url,
    create_oauth_state,
    missing_zoho_settings,
    token_url,
    verify_oauth_state,
)
from app.auth.token_store import has_refresh_token, save_tokens
from app.tools.zoho_client import projects_api_domain

router = APIRouter()


@router.get("/auth/login")
async def login():
    missing_settings = missing_zoho_settings()
    if missing_settings:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Zoho settings: {', '.join(missing_settings)}",
        )

    state = create_oauth_state()
    return RedirectResponse(build_authorization_url(state))


@router.get("/auth/callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    accounts_server: str | None = Query(default=None, alias="accounts-server"),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Zoho authorization failed: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state or not verify_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_payload = {
        "grant_type": "authorization_code",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "redirect_uri": ZOHO_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            token_response = await client.post(token_url(accounts_server), data=token_payload)
        except httpx.HTTPError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Failed to contact Zoho token endpoint.",
                    "details": str(exc),
                },
            )

    response_text = token_response.text
    try:
        tokens = token_response.json()
    except ValueError:
        return JSONResponse(
            status_code=502,
            content={
                "error": "Invalid token response from Zoho",
                "status_code": token_response.status_code,
                "body": response_text,
            },
        )

    if token_response.is_error:
        return JSONResponse(
            status_code=token_response.status_code,
            content={
                "error": "Zoho token endpoint returned an error",
                "details": tokens,
            },
        )

    token_data = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "api_domain": tokens.get("api_domain"),
        "accounts_server": accounts_server,
        "expires_in": tokens.get("expires_in"),
        "expires_at": int(time.time()) + int(tokens.get("expires_in", 3600)) - 60,
        "token_type": tokens.get("token_type"),
    }
    token_data["projects_api_domain"] = projects_api_domain(token_data)
    save_tokens(token_data)

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect = RedirectResponse(f"{frontend_url}/chat", status_code=302)
    redirect.headers["Cache-Control"] = "no-store"
    return redirect


@router.get("/auth/status")
async def status():
    return {"connected": has_refresh_token()}
