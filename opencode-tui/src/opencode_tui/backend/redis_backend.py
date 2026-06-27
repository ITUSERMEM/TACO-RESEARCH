"""Redis 后端实现。

将现有 dashbaord.py 的 Redis pub/sub + polling 逻辑迁移到此。
与 opencode 后端共享相同的 Backend 接口。
"""

import json
import os
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from opencode_tui.backend.base import Backend


class RedisBackend(Backend):
    """Redis 后端。"""

    PROGRESS_CH = "academic:progress"
    OUTBOX_CH = "academic:outbox"
    INBOX_CH = "academic:inbox"
    STATE_KEY = "academic:phase:state"

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._r = None
        self._pubsub = None
        self._connected = False

    @property
    def name(self) -> str:
        return "redis"

    async def connect(self) -> bool:
        try:
            from redis.asyncio import Redis
            self._r = Redis.from_url(self.redis_url, decode_responses=True)
            await self._r.ping()
            self._connected = True
            self._pubsub = self._r.pubsub()
            await self._pubsub.subscribe(self.PROGRESS_CH, self.OUTBOX_CH)
            return True
        except Exception:
            return False

    async def disconnect(self):
        self._connected = False
        if self._pubsub:
            await self._pubsub.unsubscribe()
        if self._r:
            await self._r.close()

    async def send_message(self, text: str) -> str:
        msg = json.dumps({
            "type": "user_message",
            "chat_id": "opencode-tui",
            "text": text,
        })
        await self._r.publish(self.INBOX_CH, msg)
        return ""

    async def subscribe(self) -> AsyncIterator[dict]:
        while self._connected:
            try:
                msg = await self._pubsub.get_message(
                    timeout=1.0, ignore_subscribe_messages=True
                )
            except Exception:
                break
            if msg is None:
                continue
            try:
                data = json.loads(msg["data"])
                channel = msg.get("channel", b"").decode() if isinstance(msg.get("channel"), bytes) else msg.get("channel", "")
                data["_source"] = "redis"
                data["_channel"] = channel
                yield data
            except (json.JSONDecodeError, Exception):
                continue

    async def get_phase_state(self) -> dict:
        try:
            state = await self._r.json().get(self.STATE_KEY)
            return state or {"status": "idle", "current_phase": 0, "completed_phases": []}
        except Exception:
            return {"status": "idle", "current_phase": 0, "completed_phases": []}

    async def get_cost_summary(self) -> dict:
        return {"session_cost": 0.0, "task_cost": 0.0, "total_cost": 0.0}

    async def get_gate_results(self) -> dict:
        try:
            state = await self._r.json().get(self.STATE_KEY)
            return (state or {}).get("gate_results", {})
        except Exception:
            return {}

    async def get_project_info(self) -> dict:
        try:
            state = await self._r.json().get(self.STATE_KEY)
            if state:
                return {
                    "title": state.get("project_title", ""),
                    "status": state.get("status", "idle"),
                    "project_id": state.get("project_id", ""),
                }
        except Exception:
            pass
        return {"title": "", "status": "disconnected", "project_id": ""}

    async def get_available_agents(self) -> list[dict]:
        return []

    async def get_available_models(self) -> list[dict]:
        return []

    def is_connected(self) -> bool:
        return self._connected
