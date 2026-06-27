"""抽象 Backend 接口。

TUI 不直接消费 Redis pub/sub 或 opencode SSE。
所有事件通过 `Backend` 接口的 `subscribe` 方法流式输出，
由 App 层转发为 Textual Message。
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional


class Backend(ABC):
    """Backend interface — TUI 切换后端不感知具体实现。"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """连接后端，返回是否成功。"""
        ...

    @abstractmethod
    async def disconnect(self):
        ...

    @abstractmethod
    async def send_message(self, text: str) -> str:
        """发送用户消息，返回消息 ID。"""
        ...

    @abstractmethod
    async def subscribe(self) -> AsyncIterator[dict]:
        """订阅事件流。每个 yield 返回一个事件 dict。

        ！！！！这是 TUI 的唯一数据源！！！！
        App 层从这里读取事件 → 转换为 Textual Message → 更新 widget。
        """
        ...

    @abstractmethod
    async def get_phase_state(self) -> dict:
        ...

    @abstractmethod
    async def get_cost_summary(self) -> dict:
        ...

    @abstractmethod
    async def get_gate_results(self) -> dict:
        ...

    @abstractmethod
    async def get_project_info(self) -> dict:
        ...

    @abstractmethod
    async def get_available_agents(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_available_models(self) -> list[dict]:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...
