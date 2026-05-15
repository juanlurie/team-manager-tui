import asyncio
import os
from typing import Any

import httpx

BASE_URL = os.environ.get("TEAM_MANAGER_API_URL", "http://localhost:5000")
API_KEY = os.environ.get("TEAM_MANAGER_API_KEY")

_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    if API_KEY:
        return {"X-API-Key": API_KEY}
    return {}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=BASE_URL, timeout=15)
    return _client


async def _get(path: str, params: dict | None = None) -> Any:
    r = await client().get(path, params={k: v for k, v in (params or {}).items() if v is not None}, headers=_headers())
    r.raise_for_status()
    return r.json()


async def _post(path: str, json: dict | None = None) -> Any:
    r = await client().post(path, json=json, headers=_headers())
    r.raise_for_status()
    return r.json()


async def get_sprints() -> list[dict]:
    return await _get("/api/v1/sprints")


async def get_sprint_dashboard(sprint_id: str) -> dict:
    return await _get(f"/api/v1/dashboard/sprint/{sprint_id}")


async def get_sprint_blockers(sprint_id: str) -> list[dict]:
    return await _get(f"/api/v1/dashboard/sprint/{sprint_id}/blockers")


async def get_leave_summary(sprint_id: str) -> dict | None:
    return await _get(f"/api/v1/dashboard/sprint/{sprint_id}/leave-summary")


async def get_work_items(sprint_member_id: str) -> list[dict]:
    return await _get(f"/api/v1/sprint-members/{sprint_member_id}/work-items")


async def create_feature(sprint_id: str, payload: dict) -> dict:
    body = {k: v for k, v in payload.items() if v is not None}
    return await _post(f"/api/v1/sprints/{sprint_id}/features", json=body)


async def load_dashboard_data(sprint_id: str) -> tuple[dict, list[dict], dict | None]:
    """Fetch dashboard, blockers, and leave summary in parallel."""
    return await asyncio.gather(
        get_sprint_dashboard(sprint_id),
        get_sprint_blockers(sprint_id),
        get_leave_summary(sprint_id),
    )
