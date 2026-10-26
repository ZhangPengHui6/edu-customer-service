"""调用客服服务内部工具接口。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from edu_ai.agent.runtime import AgentRuntimeContext
from edu_ai.config import Settings, get_settings


class CustomerServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class CustomerServiceClient:
    """以受信内部身份访问客服服务；租户与用户来自运行时上下文。"""

    def __init__(
        self,
        context: AgentRuntimeContext,
        settings: Settings | None = None,
    ):
        self.context = context
        self.settings = settings or get_settings()

    async def get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        return await self._request(
            "POST", path, payload=payload, idempotency_key=idempotency_key
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {
            "X-Internal-Service-Token": self.settings.internal_service_token,
            "X-Tenant-Id": self.context.tenant_id,
            "X-User-Id": self.context.user_id,
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = f"{self.settings.customer_service_url.rstrip('/')}{path}"
        timeout = httpx.Timeout(
            self.settings.customer_service_timeout_seconds, connect=5
        )
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.request(
                    method, url, headers=headers, json=payload
                )
        except httpx.HTTPError as exc:
            raise CustomerServiceError(503, f"客服服务不可用：{exc}") from exc

        if response.status_code >= 400:
            detail = _extract_detail(response)
            raise CustomerServiceError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"客服服务返回 {response.status_code}"
    if isinstance(body, dict) and body.get("detail"):
        return str(body["detail"])
    return f"客服服务返回 {response.status_code}"


def quote_resource(value: str) -> str:
    return quote(value.strip(), safe="")
