"""opencode-tui 主应用。

融合 opencode 视觉风格 + 双后端（Redis / opencode API）。
事件流由 Backend 抽象层屏蔽，App 层统一处理。
"""

import argparse
import asyncio
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, TextArea, Static

from opencode_tui.css import CSS
from opencode_tui.theme import TEXT_MUTED, BG_PANEL
from opencode_tui.widgets import (
    ChatPanel, PromptInput, Sidebar,
    user_message, assistant_message, system_message,
    message_footer, tool_header, tool_output,
)
from opencode_tui.backend import Backend, RedisBackend, OpenCodeBackend

from opencode_tui.widgets.phase_ring import PhaseRing
from opencode_tui.widgets.cost_budget import CostBudget
from opencode_tui.widgets.gate_status import GateStatus
from opencode_tui.widgets.agent_activity import AgentActivity
from opencode_tui.widgets.sidebar import ProjectInfo

COMMANDS = {
    "/help":   "显示命令列表",
    "/clear":  "清空聊天",
    "/mode":   "切换后端 (redis/opencode)",
    "/status": "查看管线状态",
    "/connect": "重新连接后端",
    "/diag":   "诊断信息",
}


class DashboardApp(App):
    """opencode-tui 主应用。"""

    CSS = CSS
    TITLE = "opencode-tui"
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("escape", "focus_chat", "聊天", show=False),
        Binding("ctrl+l", "clear_chat", "清屏", show=False),
    ]

    def __init__(self, redis_url: str = "redis://localhost:6379", **kwargs):
        super().__init__(**kwargs)
        self.redis_url = redis_url
        self._mode = "redis"
        self._backend: Optional[Backend] = None
        self._event_task: Optional[asyncio.Task] = None
        self._connected = False
        self._polling_task: Optional[asyncio.Task] = None

    # ── Compose ──────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="left-panel"):
                yield ChatPanel(id="chat-panel")
                yield PromptInput(id="input-area")
            yield Sidebar(id="right-panel")
        yield Footer()

    async def on_mount(self):
        self.query_one(Header).tall = False
        await self._connect_backend()

    # ── Backend Connection ───────────────────────────

    async def _connect_backend(self):
        if self._backend:
            await self._disconnect_backend()

        chat = self.query_one(ChatPanel)
        chat.write(f"[dim {TEXT_MUTED}]┃ 正在连接 {self._mode} 后端...[/]")

        if self._mode == "redis":
            self._backend = RedisBackend(redis_url=self.redis_url)
        else:
            password = ""
            try:
                from opencode_tui.client.http import DEFAULT_BASE
                password = __import__("os").environ.get("OPENCODE_SERVER_PASSWORD", "")
            except Exception:
                pass
            self._backend = OpenCodeBackend(password=password)

        ok = await self._backend.connect()
        self._connected = ok

        pi = self.query_one("#project-info", Static)
        mode_c = "#fab283" if self._mode == "opencode" else "#5c9cf5"
        status_text = "connected" if ok else "disconnected"
        status_color = "#7fd88f" if ok else "#e06c75"
        pi.update(
            f"[bold #eeeeee]opencode-tui[/]\n"
            f"[{status_color}]{status_text} · [/]"
            f"[{mode_c}]◉ {self._mode}[/]"
        )

        if ok:
            chat.write(
                f"[dim {TEXT_MUTED}]┃ [{status_color}]✓[/]"
                f" {self._mode} 后端已连接[/]"
            )
            self._start_event_tasks()
            self._start_polling()
        else:
            chat.write(
                f"[dim {TEXT_MUTED}]┃ [{status_color}]✗[/]"
                f" {self._mode} 后端不可用，显示演示数据[/]"
            )
            self._load_demo_data()

    async def _disconnect_backend(self):
        if self._event_task:
            self._event_task.cancel()
            self._event_task = None
        if self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None
        if self._backend:
            await self._backend.disconnect()

    # ── Event Tasks ──────────────────────────────────

    def _start_event_tasks(self):
        if self._event_task and not self._event_task.done():
            return
        self._event_task = asyncio.create_task(self._event_loop())

    def _start_polling(self):
        if self._polling_task and not self._polling_task.done():
            return
        self._polling_task = asyncio.create_task(self._poll_loop())

    async def _event_loop(self):
        try:
            async for event in self._backend.subscribe():
                if event is None:
                    continue
                self._on_backend_event(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._on_backend_event({
                "type": "system_error",
                "message": str(e),
            })

    async def _poll_loop(self):
        while True:
            try:
                await asyncio.sleep(3.0)
                state = await self._backend.get_phase_state()
                if state:
                    pr = self.query_one(PhaseRing)
                    pr.set_from_state(state)

                cost = await self._backend.get_cost_summary()
                if cost:
                    cb = self.query_one(CostBudget)
                    cb.update_cost(cost)
                    cb.update_budget(cost)

                gates = await self._backend.get_gate_results()
                if gates:
                    gs = self.query_one(GateStatus)
                    gs.load_from_state(gates)

                info = await self._backend.get_project_info()
                if info and info.get("title"):
                    pi = self.query_one(ProjectInfo)
                    pi.set_title(info["title"])
                    pi.set_status(info.get("status", ""))

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    # ── Event Dispatching ────────────────────────────

    def _on_backend_event(self, event: dict):
        et = event.get("type", "")
        chat = self.query_one(ChatPanel)
        aa = self.query_one(AgentActivity)

        if et == "system_error":
            chat.write(system_message(f"⚠ {event.get('message', '')}", urgent=True))
            return

        # ── Progress / Pipeline events (Redis format) ────
        if event.get("_source") == "redis":
            self._on_redis_event(event)
            return

        # ── OpenAI backend events ────────────────────────
        src = event.get("_source", "")

        if et == "chat_message":
            role = event.get("role", "")
            content = event.get("content", "")
            agent = event.get("agent", "")
            model = event.get("model", "")
            if role == "assistant" and content:
                chat.write(assistant_message(content))
                if agent:
                    chat.write(message_footer(agent, model, 0))

        elif et == "text_part":
            text = event.get("text", "")
            chat.write_stream(text, finished=event.get("finished", False))
            if text:
                aa.append_event(text[:60], "executor")

        elif et == "tool_part":
            status = event.get("status", "")
            title = event.get("title", "")
            tool = event.get("tool", "")
            output = event.get("output", "")
            err = event.get("error", "")
            display_st = "running"
            if status == "completed":
                display_st = "ok"
            elif status == "error":
                display_st = "error"
            chat.tool_block("⚙", f"{tool}: {title}", output or err, display_st)
            aa.append_event(f"{tool} {status} {title}", "executor")

        elif et == "reasoning_part":
            if event.get("finished"):
                aa.append_event("推理完成", "pro")

        elif et == "session_status":
            st = event.get("status", "")
            pi = self.query_one(ProjectInfo)
            if st == "running":
                pi.set_status("running")
            elif st == "idle":
                pi.set_status("idle")

        elif et == "session_error":
            msg = event.get("message", "")
            chat.write(system_message(f"✗ 管线错误: {msg}", urgent=True))

        elif et == "permission_asked":
            perm = event.get("permission", "")
            chat.write(system_message(f"⚠ 权限请求: {perm}", urgent=True))
            if self._backend:
                asyncio.create_task(
                    self._backend._client.reply_permission(
                        event.get("request_id", ""), "once"
                    )
                ) if hasattr(self._backend, "_client") else None

        elif et == "server_event":
            pass  # heartbeat, connected

    def _on_redis_event(self, event: dict):
        """处理 Redis 格式的 progress 事件。"""
        status = event.get("status", event.get("type", ""))
        detail = event.get("detail", "")
        phase = event.get("phase", -1)
        chat = self.query_one(ChatPanel)
        pr = self.query_one(PhaseRing)
        gs = self.query_one(GateStatus)
        cb = self.query_one(CostBudget)
        aa = self.query_one(AgentActivity)
        pi = self.query_one(ProjectInfo)

        if status == "pipeline_start":
            pr.reset_all()
            chat.write(system_message("🚀 管线启动"))
            aa.append_event("🚀 管线启动", "pro")
            pi.set_status("running")

        elif status == "phase_start":
            pr.set_phase(phase, "running")
            chat.write(
                f"[dim {TEXT_MUTED}]┃[/] ▶ Phase {phase} [{TEXT_MUTED}]"
                f"{event.get('phase_name', '')}[/]"
            )

        elif status == "phase_complete":
            pr.set_phase(phase, "done")
            chat.write(system_message(f"✓ Phase {phase} 完成"))

        elif status == "pipeline_error":
            chat.write(system_message(f"❌ 管线错误: {detail}", urgent=True))
            pi.set_status("error")

        elif status.startswith("agent_"):
            agent = detail or event.get("agent", "")
            if status == "agent_start":
                aa.append_event(f"▸ {agent}", "executor")
            elif status == "agent_done":
                aa.append_event(f"◂ {agent}", "executor")
            elif status == "agent_skill_run":
                chat.write(tool_header("⚙", agent))
            elif status == "agent_skill_ok":
                chat.write(tool_output("✓ 完成"))

        elif status.startswith("gate_"):
            gid = event.get("gate_id", 0)
            if status == "gate_pass":
                gs.update_gate(gid, "pass")
                aa.append_event(f"G{gid} PASS", "reviewer")
            elif status == "gate_revise":
                gs.update_gate(gid, "revise")
                aa.append_event(f"G{gid} REVISE", "reviewer")
            elif status == "gate_fail":
                gs.update_gate(gid, "fail")

        elif status.startswith("budget_"):
            cb.set_alert(status, detail)

    # ── Demo Data ───────────────────────────────────

    def _load_demo_data(self):
        pr = self.query_one(PhaseRing)
        pr.set_phase(0, "done")
        pr.set_phase(1, "done")
        pr.set_phase(2, "running")

        cb = self.query_one(CostBudget)
        cb.update_cost({"session_cost": 0.0234, "task_cost": 0.0891, "total_cost": 0.1125})
        cb.update_budget({"session_pct": 15, "task_pct": 42})

        gs = self.query_one(GateStatus)
        gs.update_gate(1, "pass")
        gs.update_gate(2, "pass")

        aa = self.query_one(AgentActivity)
        aa.append_event("环境初始化完成", "executor")
        aa.append_event("文献调研: 检索 12 篇相关论文", "reviewer")
        aa.append_event("方案设计进行中...", "pro")
        aa.append_event("G1 新颖性  PASS", "reviewer")
        aa.append_event("G2 实验设计  PASS (fusion)", "reviewer")

        chat = self.query_one(ChatPanel)
        chat.clear()
        chat.write("[dim #808080]opencode-tui v0.1.0 · 双后端 TUI[/]")
        chat.write("")

    # ── Input Handling ──────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed):
        if event.text_area.id != "input-textarea":
            return
        ta = event.text_area
        text = ta.text
        if "\n" in text:
            ta.text = text.replace("\n", "").strip()
            self._handle_input(text.replace("\n", "").strip())

    def _handle_input(self, text: str):
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
        elif self._connected and self._backend:
            self._send_via_backend(text)
        else:
            self._local_echo(text)

    def _handle_command(self, cmd: str):
        chat = self.query_one(ChatPanel)
        args = cmd.split()
        base = args[0].lower()

        if base == "/help":
            for c, d in COMMANDS.items():
                chat.write(f"[dim {TEXT_MUTED}]┃[/] [bold #fab283]{c:<8}[/] [dim {TEXT_MUTED}]{d}[/]")
        elif base == "/clear":
            chat.clear()
        elif base == "/mode":
            new_mode = args[1] if len(args) > 1 else ("opencode" if self._mode == "redis" else "redis")
            if new_mode not in ("redis", "opencode"):
                return
            self._mode = new_mode
            asyncio.create_task(self._connect_backend())
        elif base == "/status":
            self._show_status()
        elif base == "/connect":
            asyncio.create_task(self._connect_backend())
        elif base == "/diag":
            asyncio.create_task(self._show_diag())
        else:
            chat.write(f"[dim {TEXT_MUTED}]┃ 未知命令: {cmd}  [/][dim]使用 /help 查看列表[/]")

    def _switch_mode(self, mode: str):
        self._handle_command(f"/mode {mode}")

    def _show_status(self):
        chat = self.query_one(ChatPanel)
        backend_name = self._backend.name if self._backend else "none"
        status = "connected" if self._connected else "disconnected"
        s_color = "#7fd88f" if self._connected else "#e06c75"
        chat.write(f"[dim {TEXT_MUTED}]┃ opencode-tui 状态[/]")
        chat.write(f"[dim {TEXT_MUTED}]┃   后端:   [/][{s_color}]◉ {backend_name} ({status})[/]")
        chat.write(f"[dim {TEXT_MUTED}]┃   模式:   [/][#5c9cf5]{self._mode}[/]")

    def _send_via_backend(self, text: str):
        chat = self.query_one(ChatPanel)
        chat.write(user_message(text))
        asyncio.create_task(self._async_send(text))

    async def _async_send(self, text: str):
        try:
            input_area = self.query_one(PromptInput)
            input_area.set_busy(True)
            await self._backend.send_message(text)
        except Exception as e:
            chat = self.query_one(ChatPanel)
            chat.write(system_message(f"✗ 发送失败: {e}", urgent=True))
        finally:
            try:
                input_area = self.query_one(PromptInput)
                input_area.set_busy(False)
            except Exception:
                pass

    async def _show_diag(self):
        chat = self.query_one(ChatPanel)
        backend_name = self._backend.name if self._backend else "none"
        chat.write(f"[bold #e5c07b]── Diagnostics ──[/]")
        chat.write(f"[dim]┃  backend:     {backend_name}[/]")
        chat.write(f"[dim]┃  connected:   {self._connected}[/]")
        chat.write(f"[dim]┃  mode:        {self._mode}[/]")
        if self._backend and self._connected:
            try:
                info = await self._backend.get_project_info()
                chat.write(f"[dim]┃  project:     {info.get('title', 'N/A')}[/]")
                chat.write(f"[dim]┃  status:      {info.get('status', 'N/A')}[/]")
            except Exception:
                chat.write(f"[dim]┃  project:     (read error)[/]")
            try:
                state = await self._backend.get_phase_state()
                completed = state.get("completed_phases", [])
                chat.write(f"[dim]┃  phases:      {len(completed)}/6 complete[/]")
                chat.write(f"[dim]┃  current:     Phase {state.get('current_phase', '-')}[/]")
                chat.write(f"[dim]┃  status:      {state.get('status', '-')}[/]")
            except Exception:
                chat.write(f"[dim]┃  phases:      (read error)[/]")
        chat.write(f"[dim]┃  widgets:     {len(list(self.query('*')))}[/]")

    def _local_echo(self, text: str):
        chat = self.query_one(ChatPanel)
        chat.write(user_message(text))
        chat.write(assistant_message(f"已收到 (演示模式): {text}"))

    # ── Focus Management ───────────────────────────

    def action_focus_chat(self):
        ta = self.query_one("#input-textarea", TextArea)
        ta.focus()

    def action_clear_chat(self):
        self.query_one(ChatPanel).clear()


def main():
    parser = argparse.ArgumentParser(description="opencode-tui")
    parser.add_argument("--redis", default="redis://localhost:6379")
    parser.add_argument("--mode", choices=["redis", "opencode"], default="redis")
    args = parser.parse_args()

    app = DashboardApp(redis_url=args.redis)
    app._mode = args.mode
    app.run()


if __name__ == "__main__":
    main()
