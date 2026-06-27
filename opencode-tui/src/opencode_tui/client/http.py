"""opencode HTTP API 客户端。

封装 opencode serve 的所有 HTTP 端点调用。
使用 httpx 异步 client，支持 Basic Auth + 目录路由。
"""

import json
import os
from typing import Optional, AsyncIterator

import httpx

from opencode_tui.client.sse import SSEClient, SSEEvent


DEFAULT_BASE = "http://127.0.0.1:4096"
DEFAULT_USER = "opencode"


class OpenCodeError(Exception):
    """opencode API 错误。"""
    def __init__(self, message: str, status_code: int = 0):
        self.status_code = status_code
        super().__init__(message)


class OpenCodeClient:
    """opencode HTTP API 客户端。

    用法:
        client = OpenCodeClient(password="my-pass")
        session = await client.create_session()
        async for event in client.subscribe():
            ...
        msg = await client.send_prompt(session["id"], "hello")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        password: str = "",
        directory: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self._password = password
        self._directory = directory or os.getcwd()
        self._session_id: Optional[str] = None
        self._http: Optional[httpx.AsyncClient] = None

    def _get_auth(self) -> Optional[httpx.BasicAuth]:
        if self._password:
            return httpx.BasicAuth(DEFAULT_USER, self._password)
        return None

    def _url(self, path: str, **params) -> str:
        qs = f"?directory={self._directory}"
        if params:
            qs += "&" + "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}{path}{qs}"

    # ── Lifecycle ────────────────────────────────────

    async def connect(self) -> bool:
        """测试连接。"""
        try:
            self._http = httpx.AsyncClient(auth=self._get_auth())
            resp = await self._http.get(self._url("/global/health"))
            if resp.status_code == 401:
                raise OpenCodeError("鉴权失败: OPENCODE_SERVER_PASSWORD 未正确设置", 401)
            data = resp.json()
            return data.get("healthy", False)
        except httpx.ConnectError:
            return False

    async def close(self):
        if self._http:
            await self._http.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        assert self._http is not None, "client not connected, call connect() first"
        return self._http

    # ── Session ──────────────────────────────────────

    async def list_sessions(self) -> list[dict]:
        resp = await self.http.get(self._url("/session"))
        self._raise_for_status(resp, "list sessions")
        return resp.json()

    async def get_session(self, session_id: str) -> dict:
        resp = await self.http.get(self._url(f"/session/{session_id}"))
        self._raise_for_status(resp, "get session")
        return resp.json()

    async def create_session(
        self,
        agent: str = "",
        model: str = "",
        title: str = "",
    ) -> dict:
        """创建新 session。所有字段可选。"""
        body: dict = {}
        if agent:
            body["agent"] = agent
        if model:
            body["model"] = {"id": model}
        if title:
            body["title"] = title
        resp = await self.http.post(
            self._url("/session"),
            json=body,
        )
        self._raise_for_status(resp, "create session")
        data = resp.json()
        self._session_id = data.get("id")
        return data

    async def fork_session(self, session_id: str) -> dict:
        resp = await self.http.post(self._url(f"/session/{session_id}/fork"))
        self._raise_for_status(resp, "fork session")
        data = resp.json()
        self._session_id = data.get("id")
        return data

    async def delete_session(self, session_id: str):
        resp = await self.http.delete(self._url(f"/session/{session_id}"))
        self._raise_for_status(resp, "delete session")

    # ── Prompt ───────────────────────────────────────

    async def send_prompt(self, session_id: str, text: str, **kwargs) -> dict:
        """发送 prompt，返回 assistant 消息记录。

        kwargs 可包含 agent, model 等。
        """
        body = {
            "parts": [{"type": "text", "text": text}],
        }
        if kwargs.get("agent"):
            body["agent"] = kwargs["agent"]
        if kwargs.get("model"):
            body["model"] = {"id": kwargs["model"]}
        resp = await self.http.post(
            self._url(f"/session/{session_id}/message"),
            json=body,
        )
        self._raise_for_status(resp, "send prompt")
        return resp.json()

    async def send_command(self, session_id: str, command: str, **kwargs) -> dict:
        """发送 slash 命令。"""
        body = {"command": command, "arguments": " ".join(kwargs.pop("args", []))}
        if kwargs.get("agent"):
            body["agent"] = kwargs["agent"]
        resp = await self.http.post(
            self._url(f"/session/{session_id}/command"),
            json=body,
        )
        self._raise_for_status(resp, "send command")
        return resp.json()

    # ── Permission ───────────────────────────────────

    async def reply_permission(self, request_id: str, reply: str = "once"):
        """回复权限请求。reply: once | always | reject"""
        resp = await self.http.post(
            self._url(f"/permission/{request_id}/reply"),
            json={"reply": reply},
        )
        self._raise_for_status(resp, "reply permission")

    # ── Agent / Provider / Config ────────────────────

    async def list_agents(self) -> list[dict]:
        resp = await self.http.get(self._url("/agent"))
        self._raise_for_status(resp, "list agents")
        return resp.json()

    async def list_providers(self) -> list[dict]:
        resp = await self.http.get(self._url("/provider"))
        self._raise_for_status(resp, "list providers")
        return resp.json()

    # ── Event Stream ─────────────────────────────────

    async def subscribe(
        self,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """订阅 SSE 事件流。

        每次 yield 一个事件 dict: {id, type, properties}
        如果指定 session_id，只 yield 该 session 的事件。
        """
        async with self.http.stream(
            "GET",
            self._url("/event"),
        ) as response:
            self._raise_for_status(response, "subscribe events")
            async for event in SSEClient.iter_events(response):
                if session_id:
                    props = event.properties
                    if props.get("sessionID") and props["sessionID"] != session_id:
                        continue
                yield {
                    "id": event.id,
                    "type": event.type,
                    "properties": event.properties,
                }

    async def wait_until_idle(
        self,
        session_id: str,
        timeout: float = 300.0,
    ) -> AsyncIterator[dict]:
        """消费 SSE 流直到 session 状态变为 idle。"""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        async for event in self.subscribe(session_id=session_id):
            if asyncio.get_event_loop().time() > deadline:
                yield {"type": "timeout", "properties": {}}
                break
            yield event
            if event["type"] == "session.status":
                status = event["properties"].get("status", {})
                if isinstance(status, dict) and status.get("type") == "idle":
                    break
            if event["type"] in ("session.error", "server.instance.disposed"):
                break

    # ── Helpers ──────────────────────────────────────

    def _raise_for_status(self, resp, context: str):
        if resp.status_code >= 400:
            try:
                detail = resp.text[:500]
            except Exception:
                detail = ""
            raise OpenCodeError(
                f"{context} failed ({resp.status_code}): {detail}",
                resp.status_code,
            )

    @property
    def current_session_id(self) -> Optional[str]:
        return self._session_id
