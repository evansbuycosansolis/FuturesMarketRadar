"""A fixed-route bridge to the research-only Agentic service. No trading proxy."""
from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException


class DeskBridge:
    def __init__(self, origin: str):
        parsed = urlsplit(origin)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            raise ValueError("The desk service must use a loopback HTTP origin.")
        self.origin = origin.rstrip("/")

    async def call(self, method: str, resource: str, *, params=None, body=None, token=None):
        allowed = {("GET", "status"), ("GET", "conversations"), ("GET", "messages"),
                   ("GET", "market"), ("POST", "conversations"), ("POST", "chat"),
                   ("POST", "settings")}
        if (method, resource) not in allowed:
            raise HTTPException(403, "This route is outside the research desk allowlist.")
        headers = {"X-Desk-Token": token} if token else {}
        try:
            async with httpx.AsyncClient(timeout=600, trust_env=False, follow_redirects=False) as client:
                response = await client.request(method, self.origin + "/api/" + resource,
                                                params=params, json=body, headers=headers)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "The OpenAI desk service is unavailable. Start it with the integrated launcher.") from exc
        if response.status_code >= 400:
            raise HTTPException(response.status_code, str(data.get("error", "Desk request failed.")))
        if response.is_redirect:
            raise HTTPException(502, "The desk service returned an unexpected redirect.")
        return data
