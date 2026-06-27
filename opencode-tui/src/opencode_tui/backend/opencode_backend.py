"""opencode HTTP API 后端实现。

将 opencode serve 的 SSE 事件流映射为 Backend 接口。
事件转换为与 Redis 后端兼容的 dict 格式，
App 层无需关心事件来源。
"""

import os
from typing import AsyncIterator, Optional

from opencode_tui.backend.base import Backend
from opencode_tui.client.http import OpenCodeClient, OpenCodeError
from opencode_tui.client.sse import SSEEvent


SESSION_STATUS_MAP = {
    "idle": "idle",
    "busy": "running",
    "retry": "running",
}


class OpenCodeBackend(Backend):
    """opencode HTTP API 后端。"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:4096",
        password: str = "",
        directory: str = "",
    ):
        self._client = OpenCodeClient(
            base_url=base_url,
            password=password or os.environ.get("OPENCODE_SERVER_PASSWORD", ""),
            directory=directory or os.getcwd(),
        )
        self._session: Optional[dict] = None
        self._connected = False

    @property
    def name(self) -> str:
        return "opencode"

    async def connect(self) -> bool:
        try:
            ok = await self._client.connect()
            if ok:
                self._connected = True
            return ok
        except Exception:
            return False

    async def disconnect(self):
        self._connected = False
        await self._client.close()

    def is_connected(self) -> bool:
        return self._connected

    async def send_message(self, text: str) -> str:
        if not self._session:
            self._session = await self._client.create_session()
        await self._client.send_prompt(self._session["id"], text)
        return ""

    async def subscribe(self) -> AsyncIterator[dict]:
        if not self._session:
            self._session = await self._client.create_session()
        sid = self._session["id"]

        async for raw in self._client.subscribe(session_id=sid):
            event_type = raw["type"]
            props = raw["properties"]

            mapped = self._map_event(event_type, props)
            if mapped:
                yield mapped

    def _map_event(self, event_type: str, props: dict) -> Optional[dict]:
        """将 opencode SSE 事件映射为 Backend 通用格式。"""
        source = {
            "_source": "opencode",
            "_session_id": self._session["id"] if self._session else "",
        }

        # ── 消息事件 ─────────────────────────────────
        if event_type == "message.updated":
            info = props.get("info", {})
            role = info.get("role", "")
            if role == "assistant":
                return {
                    "type": "chat_message",
                    "role": "assistant",
                    "content": info.get("summary", ""),
                    "agent": (info.get("agent") or ""),
                    "model": (info.get("model") or {}).get("id", ""),
                    "finish": info.get("finish"),
                    **source,
                }

        # ── Part 更新（流式文本/工具/推理）───────────
        elif event_type == "message.part.updated":
            part = props.get("part", {})
            pt = part.get("type", "")
            if pt == "text":
                return {
                    "type": "text_part",
                    "text": part.get("text", ""),
                    "synthetic": part.get("synthetic", False),
                    "finished": part.get("time", {}).get("end") is not None,
                    **source,
                }
            elif pt == "tool":
                state = part.get("state", {})
                status = state.get("status", "pending")
                call_id = part.get("callID", "")
                tool = part.get("tool", "")
                return {
                    "type": "tool_part",
                    "status": status,
                    "call_id": call_id,
                    "tool": tool,
                    "title": state.get("title", ""),
                    "input": state.get("input", ""),
                    "output": state.get("output", ""),
                    "error": state.get("error", ""),
                    **source,
                }
            elif pt == "reasoning":
                return {
                    "type": "reasoning_part",
                    "text": part.get("text", ""),
                    "finished": part.get("time", {}).get("end") is not None,
                    **source,
                }
            elif pt == "step-start":
                return {"type": "step_start", **source}
            elif pt == "step-finish":
                reason = part.get("reason", "")
                return {"type": "step_finish", "reason": reason, **source}

        # ── Session 状态 ─────────────────────────────
        elif event_type == "session.status":
            st = props.get("status", {})
            if isinstance(st, dict):
                st_type = st.get("type", "idle")
                return {
                    "type": "session_status",
                    "status": SESSION_STATUS_MAP.get(st_type, st_type),
                    **source,
                }

        # ── Session 错误 ─────────────────────────────
        elif event_type == "session.error":
            err = props.get("error", {})
            return {
                "type": "session_error",
                "message": (err.get("data") or {}).get("message", "") or err.get("name", ""),
                **source,
            }

        # ── 权限 ─────────────────────────────────────
        elif event_type == "permission.asked":
            return {
                "type": "permission_asked",
                "request_id": props.get("id", ""),
                "permission": props.get("permission", ""),
                **source,
            }

        # ── server.connected / heartbeat ─────────────
        elif event_type in ("server.connected", "server.heartbeat"):
            return {"type": "server_event", "event": event_type, **source}

        return None

    # ── Pull-based APIs ──────────────────────────────

    async def get_phase_state(self) -> dict:
        """opencode 模式下无 phase 概念，返回空状态。"""
        return {"status": "idle", "current_phase": 0, "completed_phases": []}

    async def get_cost_summary(self) -> dict:
        return {"session_cost": 0.0, "task_cost": 0.0, "total_cost": 0.0}

    async def get_gate_results(self) -> dict:
        return {}

    async def get_project_info(self) -> dict:
        return {"title": "opencode session", "status": "connected"}

    async def get_available_agents(self) -> list[dict]:
        try:
            return await self._client.list_agents()
        except Exception:
            return []

    async def get_available_models(self) -> list[dict]:
        try:
            return await self._client.list_providers()
        except Exception:
            return []
