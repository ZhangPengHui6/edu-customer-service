"""调用 AI 服务的内部客户端。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from edu_cs.config import Settings, get_settings


class AIServiceError(RuntimeError):
    """AI 服务返回错误或不可用。"""


class AIServiceNotFoundError(AIServiceError):
    """AI 服务没有对应的记录（如运行 ID 不存在或跨租户）。"""


class AIServiceClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self._post_json("/internal/v1/agent/runs", request)

    async def confirm_run(
        self, run_id: str, input_revision: int
    ) -> dict[str, Any]:
        return await self._post_json(
            f"/internal/v1/agent/runs/{run_id}/confirm",
            {"input_revision": input_revision},
        )

    async def cancel_run(self, run_id: str) -> None:
        await self._post(
            f"/internal/v1/agent/runs/{run_id}/cancel",
            None,
            expected_status=(204,),
        )

    async def list_runs(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        conversation_id: UUID | None = None,
        turn_id: UUID | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """运营侧查询 Agent 运行记录。"""
        params: dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit}
        if status is not None:
            params["status"] = status
        if conversation_id is not None:
            params["conversation_id"] = str(conversation_id)
        if turn_id is not None:
            params["turn_id"] = str(turn_id)
        return await self._get_json("/internal/v1/agent/runs", params)

    async def get_run(
        self, run_id: str, *, tenant_id: UUID | None = None
    ) -> dict[str, Any]:
        params = {"tenant_id": str(tenant_id)} if tenant_id else None
        return await self._get_json(f"/internal/v1/agent/runs/{run_id}", params)

    async def list_tool_calls(
        self, run_id: str, *, tenant_id: UUID | None = None
    ) -> dict[str, Any]:
        params = {"tenant_id": str(tenant_id)} if tenant_id else None
        return await self._get_json(
            f"/internal/v1/agent/runs/{run_id}/tool-calls", params
        )

    async def _post_json(
        self, path: str, payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        response = await self._post(path, payload)
        event = response.json()
        if not isinstance(event, dict) or "event_type" not in event:
            raise AIServiceError("AI 服务返回了不符合约定的事件")
        return event

    async def _get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {
            "X-Internal-Service-Token": self.settings.internal_service_token,
            "Accept": "application/json",
        }
        # 查询接口不应占满调用 AI 的长超时。
        timeout = httpx.Timeout(
            min(self.settings.ai_timeout_seconds, 30.0), connect=5
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout, trust_env=False
            ) as client:
                response = await client.get(
                    f"{self.settings.ai_service_url.rstrip('/')}{path}",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AIServiceNotFoundError("AI 运行记录不存在") from exc
            raise AIServiceError(f"AI 服务调用失败：{exc}") from exc
        except httpx.HTTPError as exc:
            raise AIServiceError(f"AI 服务调用失败：{exc}") from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise AIServiceError("AI 服务返回了不符合约定的数据")
        return payload

    async def _post(
        self,
        path: str,
        payload: dict[str, Any] | None,
        *,
        expected_status: tuple[int, ...] = (200,),
    ) -> httpx.Response:
        headers = {
            "X-Internal-Service-Token": self.settings.internal_service_token,
            "Accept": "application/json",
        }
        timeout = httpx.Timeout(self.settings.ai_timeout_seconds, connect=5)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, trust_env=False
            ) as client:
                response = await client.post(
                    f"{self.settings.ai_service_url.rstrip('/')}{path}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIServiceError(f"AI 服务调用失败：{exc}") from exc

        if response.status_code not in expected_status:
            raise AIServiceError(
                f"AI 服务返回了非预期状态码 {response.status_code}"
            )
        return response
