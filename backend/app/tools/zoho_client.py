import time
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException

from app.auth.login import ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, token_url
from app.auth.token_store import load_tokens, save_tokens


def parse_zoho_response(response: httpx.Response) -> Any:
    text = response.text.strip()
    if not text:
        return {
            "empty": True,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "url": str(response.request.url),
        }

    try:
        return response.json()
    except ValueError:
        if text.startswith("<"):
            try:
                return xml_to_dict(ElementTree.fromstring(text))
            except ElementTree.ParseError:
                pass
        return {
            "content_type": response.headers.get("content-type"),
            "message": text[:1000],
            "status_code": response.status_code,
            "url": str(response.request.url),
        }


def xml_to_dict(element: ElementTree.Element) -> dict[str, Any] | str:
    children = list(element)
    if not children:
        return element.text or ""

    parsed: dict[str, Any] = {}
    for child in children:
        child_value = xml_to_dict(child)
        if child.tag in parsed:
            if not isinstance(parsed[child.tag], list):
                parsed[child.tag] = [parsed[child.tag]]
            parsed[child.tag].append(child_value)
        else:
            parsed[child.tag] = child_value
    return {element.tag: parsed}


def parse_zoho_error(response: httpx.Response) -> Any:
    error = parse_zoho_response(response)
    if response.status_code == 403 and "invalid auth scope" in str(error).lower():
        return {
            "message": "Zoho token is missing the required Projects scope. Update ZOHO_SCOPES and visit /auth/login again.",
            "zoho_error": error,
            "url": str(response.request.url),
        }
    return error


def projects_api_domain(tokens: dict[str, Any]) -> str:
    stored_domain = tokens.get("projects_api_domain")
    if stored_domain:
        return stored_domain.rstrip("/")

    accounts_server = tokens.get("accounts_server") or ""
    accounts_host = urlparse(accounts_server).netloc
    if accounts_host.endswith(".in"):
        return "https://projectsapi.zoho.in"
    if accounts_host.endswith(".eu"):
        return "https://projectsapi.zoho.eu"
    if accounts_host.endswith(".com.au"):
        return "https://projectsapi.zoho.com.au"
    if accounts_host.endswith(".jp"):
        return "https://projectsapi.zoho.jp"
    if accounts_host.endswith(".ca"):
        return "https://projectsapi.zoho.ca"

    return "https://projectsapi.zoho.com"


async def get_access_token() -> str:
    tokens = load_tokens()
    access_token = tokens.get("access_token")
    expires_at = int(tokens.get("expires_at") or 0)

    if access_token and expires_at > int(time.time()):
        return access_token

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Zoho is not connected. Visit /auth/login first.",
        )

    payload = {
        "grant_type": "refresh_token",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    accounts_server = tokens.get("accounts_server")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(token_url(accounts_server), params=payload)

    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail=parse_zoho_error(response))

    refreshed_tokens = response.json()
    expires_in = int(refreshed_tokens.get("expires_in", 3600))
    save_tokens(
        {
            "access_token": refreshed_tokens.get("access_token"),
            "api_domain": refreshed_tokens.get("api_domain") or tokens.get("api_domain"),
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in - 60,
            "token_type": refreshed_tokens.get("token_type", "Bearer"),
        }
    )
    return refreshed_tokens["access_token"]


async def zoho_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response_data = await zoho_request(path, params=params)

    if response_data["is_error"]:
        raise HTTPException(
            status_code=response_data["status_code"],
            detail=response_data["body"],
        )

    parsed_response = response_data["body"]
    if isinstance(parsed_response, dict) and (
        parsed_response.get("content_type") or parsed_response.get("empty")
    ):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Zoho returned an empty or non-JSON response.",
                "zoho_response": parsed_response,
            },
        )

    return parsed_response


async def zoho_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    tokens = load_tokens()
    api_domain = projects_api_domain(tokens)
    if not api_domain:
        raise HTTPException(
            status_code=401,
            detail="Zoho Projects API domain is missing. Visit /auth/login first.",
        )

    access_token = await get_access_token()
    url = f"{api_domain}{path}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers=headers, params=params)

    body = parse_zoho_error(response) if response.is_error else parse_zoho_response(response)
    return {
        "body": body,
        "is_error": response.is_error,
        "path": path,
        "status_code": response.status_code,
        "url": str(response.url),
    }


async def zoho_send(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tokens = load_tokens()
    api_domain = projects_api_domain(tokens)
    if not api_domain:
        raise HTTPException(
            status_code=401,
            detail="Zoho Projects API domain is missing. Visit /auth/login first.",
        )

    access_token = await get_access_token()
    url = f"{api_domain}{path}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.request(method, url, headers=headers, params=params, json=json_body)

    body = parse_zoho_error(response) if response.is_error else parse_zoho_response(response)
    response_data = {
        "body": body,
        "is_error": response.is_error,
        "path": path,
        "status_code": response.status_code,
        "url": str(response.url),
    }
    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail=body)
    return response_data


async def create_task(portal_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await zoho_send(
        "POST",
        f"/api/v3/portal/{portal_id}/projects/{project_id}/tasks",
        json_body=payload,
    )


async def update_task(
    portal_id: str,
    project_id: str,
    task_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await zoho_send(
        "PATCH",
        f"/api/v3/portal/{portal_id}/projects/{project_id}/tasks/{task_id}",
        json_body=payload,
    )


async def delete_task(portal_id: str, project_id: str, task_id: str) -> dict[str, Any]:
    return await zoho_send(
        "DELETE",
        f"/api/v3/portal/{portal_id}/projects/{project_id}/tasks/{task_id}",
    )


async def get_portals() -> dict[str, Any]:
    return await zoho_get("/api/v3/portals")


async def get_projects(portal_id: str) -> dict[str, Any]:
    return await zoho_get(f"/api/v3/portal/{portal_id}/projects")


async def get_tasks(portal_id: str, project_id: str) -> dict[str, Any]:
    return await zoho_get(f"/api/v3/portal/{portal_id}/projects/{project_id}/tasks")


async def debug_portal_endpoints() -> list[dict[str, Any]]:
    results = []
    for path, params in portal_endpoint_candidates():
        try:
            results.append(await zoho_request(path, params=params))
        except HTTPException as error:
            results.append({"path": path, "status_code": error.status_code, "body": error.detail})
    return results


def portal_endpoint_candidates() -> list[tuple[str, dict[str, Any] | None]]:
    return [
        ("/api/v3/portals", None),
        ("/api/v3/portal", None),
        ("/restapi/portals/", {"format": "json"}),
    ]
