#!/usr/bin/env python3
"""Telegram Bot bridge for opencode CLI running in tmux."""

import asyncio
import io
import json
import logging
import os
import subprocess
import time
from typing import Optional

import redis as redis_module
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ── Config ──────────────────────────────────────────────────
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "bot_token.txt")
if "TELEGRAM_BOT_TOKEN" in os.environ:
    BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
elif os.path.exists(_TOKEN_FILE):
    with open(_TOKEN_FILE) as f:
        BOT_TOKEN = f.read().strip()
else:
    raise RuntimeError(f"TELEGRAM_BOT_TOKEN not set and {_TOKEN_FILE} not found")
TMUX_SESSION = "opencode"
TMUX_PANE_HEIGHT = 120
TMUX_HISTORY_LIMIT = 50000
POLL_INTERVAL = 0.8
STABLE_SECONDS = 3.0
MAX_TIMEOUT = 180.0
MAX_RESPONSE_LEN = 3800

# ── Redis pub/sub for AcademicLoop bridge ──
REDIS_INBOX = "academic:inbox"
REDIS_OUTBOX = "academic:outbox"
_redis_client: Optional["redis_module.Redis"] = None

def _get_redis() -> "redis_module.Redis":
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_module.Redis.from_url("redis://localhost:6379", decode_responses=True)
    return _redis_client

LOOP_ENABLED = True  # AcademicLoop daemon auto-executes pipeline on user_message

def academic_loop_available() -> bool:
    if not LOOP_ENABLED:
        return False
    try:
        r = _get_redis()
        num_subs = r.execute_command("PUBSUB NUMSUB " + REDIS_INBOX)
        return num_subs and len(num_subs) >= 2 and num_subs[1] > 0
    except Exception:
        return False

_msg_lock = asyncio.Lock()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg_bridge")


# ── Tmux Helpers ────────────────────────────────────────────

def _tmux(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux"] + args,
        capture_output=True, text=True, timeout=timeout,
    )


def session_alive() -> bool:
    p = _tmux(["has-session", "-t", TMUX_SESSION])
    return p.returncode == 0


def session_create():
    _tmux(["set-option", "-g", "history-limit", str(TMUX_HISTORY_LIMIT)], timeout=3)
    _tmux(["new-session", "-d", "-s", TMUX_SESSION, "-x", "120",
           "-y", str(TMUX_PANE_HEIGHT), "opencode"], timeout=10)
    logger.info("Created tmux session '%s' (h=%d, history=%d)",
                TMUX_SESSION, TMUX_PANE_HEIGHT, TMUX_HISTORY_LIMIT)


def session_kill():
    _tmux(["kill-session", "-t", TMUX_SESSION])
    logger.info("Killed tmux session '%s'", TMUX_SESSION)


def session_respawn():
    session_kill()
    time.sleep(0.5)
    session_create()


def capture_pane() -> tuple[str, int]:
    """Capture pane content. Returns (text, line_count)."""
    p = _tmux(["capture-pane", "-t", TMUX_SESSION, "-p", "-e", "-S", "-200"])
    if p.returncode != 0:
        return "", 0
    text = strip_ansi(p.stdout)
    return text, len(text.splitlines())


def send_keys(text: str):
    _tmux(["send-keys", "-t", TMUX_SESSION, "-l", text])
    _tmux(["send-keys", "-t", TMUX_SESSION, "Enter"])


def strip_ansi(s: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s).replace("\r\n", "\n").replace("\r", "\n")


# ── Output Extraction ───────────────────────────────────────

def _strip_bottom(content: str, n: int = 3) -> str:
    lines = content.splitlines()
    return "\n".join(lines[:-n]) if len(lines) > n else content


def extract_new_output(before_text: str, before_lines: int, after_text: str) -> str:
    """Extract new output by finding first differing line from the top."""
    a_lines = after_text.splitlines()
    b_lines = before_text.splitlines()

    if len(a_lines) > len(b_lines):
        return "\n".join(a_lines[len(b_lines):]).strip()

    min_len = min(len(b_lines), len(a_lines))
    for i in range(min_len):
        if b_lines[i] != a_lines[i]:
            return "\n".join(a_lines[i:]).strip()
    return ""


def _clean_opencode_output(text: str) -> str:
    """Remove terminal UI chrome, keep only the actual response content."""
    import re
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        s = line.strip()
        if re.search(r"[\|╹╺╻╼╾┃╽╿▀▁▂▃▄▅▆▇▉▊▋▌▍▎▏─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋]", line):
            continue
        if re.search(r"Build ·|ctrl\+p\s+commands|▣|OpenCode Zen|max\s*$", s):
            continue
        if re.search(r"^\d+\.\d+[KMG]? \(\d+%\)", s):
            continue
        if re.search(r"^\s*\+?\s*Thought:", s):
            continue
        if re.search(r"^→\s*Skill", s):
            continue
        if re.search(r"^\s*Click to expand", s):
            continue
        if not s:
            continue
        cleaned.append(s)
    return "\n".join(cleaned)


# ── Polling ─────────────────────────────────────────────────

async def poll_for_output(
    before_text: str,
    before_lines: int,
    timeout: float = MAX_TIMEOUT,
) -> str:
    """Poll tmux capture until output stabilizes."""
    stable_since: Optional[float] = None
    last_stable = _strip_bottom(before_text)
    start = time.time()
    had_activity = False

    while time.time() - start < timeout:
        await asyncio.sleep(POLL_INTERVAL)
        current_text, current_lines = capture_pane()
        current_stable = _strip_bottom(current_text)

        if current_stable == last_stable:
            if stable_since is None:
                stable_since = time.time()
            elif had_activity and time.time() - stable_since >= STABLE_SECONDS:
                return extract_new_output(before_text, before_lines, current_text)
        else:
            stable_since = None
            last_stable = current_stable
            had_activity = True

    current_text, _ = capture_pane()
    return extract_new_output(before_text, before_lines, current_text)


# ── Telegram Handlers ───────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    if not session_alive():
        await update.message.reply_text("❌ opencode 会话已断开，使用 /respawn 重建")
        return

    if _msg_lock.locked():
        await update.message.reply_text("⏳ 上一个请求仍在处理中，请稍候")
        return

    async with _msg_lock:
        logger.info("[%s] %s", chat_id, user_text[:80])

        # Route to AcademicLoop if available, otherwise use tmux
        if academic_loop_available():
            await _handle_via_academic_loop(update, context, user_text, chat_id)
        else:
            await _handle_via_tmux(update, context, user_text, chat_id)


async def _handle_via_academic_loop(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    user_text: str, chat_id: int,
):
    """Send message to AcademicLoop via Redis pub/sub with live progress."""
    status_msg = await update.message.reply_text("🚀 学术团队管线启动中...")

    try:
        r = _get_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(REDIS_OUTBOX, "academic:progress")

        r.publish(REDIS_INBOX, json.dumps({
            "type": "user_message",
            "chat_id": str(chat_id),
            "text": user_text,
            "timestamp": time.time(),
        }))

        response = None
        deadline = time.time() + 300.0  # 5 min max
        while time.time() < deadline:
            msg = pubsub.get_message(timeout=0.5)
            if not msg or msg["type"] != "message":
                continue

            try:
                data = json.loads(msg["data"])
            except json.JSONDecodeError:
                continue

            channel = msg.get("channel", b"").decode() if isinstance(msg.get("channel"), bytes) else msg.get("channel", "")

            # Real-time progress
            if "progress" in str(channel):
                if str(data.get("chat_id")) != str(chat_id):
                    continue
                detail = data.get("detail", "")
                pct = data.get("progress_pct", 0)
                status = data.get("status", "")
                phase_label = data.get("phase_label", "")

                # Status updates edit the progress bar message
                STATUS_KEYS = {"pipeline_start", "pipeline_error", "phase_start",
                               "phase_complete", "gate_pass", "gate_revise", "gate_fail"}
                # Agent events get separate reply messages
                AGENT_REPLY = {"agent_start", "agent_skill_result",
                               "agent_done", "agent_skill_output",
                               "agent_skip_skill", "agent_skill_select"}

                if status in STATUS_KEYS:
                    icons = {"phase_start": "📋", "phase_complete": "✅",
                             "gate_pass": "✅", "gate_revise": "⚠️", "gate_fail": "❌",
                             "pipeline_start": "🚀", "pipeline_error": "❌"}
                    icon = icons.get(status, "🔄")
                    text = f"{icon} {detail}\n─── {pct}% ─── Phase {data.get('phase','?')} {phase_label}"
                    logger.info(">>> edit_text: %.200s", text)
                    try:
                        await status_msg.edit_text(text)
                    except Exception:
                        pass

                elif status in AGENT_REPLY:
                    logger.info(">>> reply: %.200s", detail)
                    try:
                        await update.message.reply_text(
                            f"{detail}",
                            disable_notification=True,
                        )
                    except Exception:
                        pass

                elif status == "agent_skill_run":
                    logger.info(">>> skill: %.200s", detail)
                    try:
                        await update.message.reply_text(
                            f"⚙️ {detail}",
                            disable_notification=True,
                        )
                    except Exception:
                        pass

                continue

            # Pipeline ack → update status, keep listening
            if "outbox" in str(channel) or "pipeline_result" in str(channel):
                if str(data.get("chat_id")) != str(chat_id):
                    continue
                msg_type = data.get("type", "")
                if msg_type == "pipeline_ack":
                    await status_msg.edit_text(data.get("text", "🚀 管线运行中..."))
                    continue  # keep listening for progress + result
                if msg_type == "pipeline_result":
                    response = data
                    break

        pubsub.unsubscribe()

        if not response:
            await status_msg.edit_text("✅ 学术团队管线已完成")
            return

        text = response.get("text") or json.dumps(response.get("data", {}),
                                                    indent=2, ensure_ascii=False)
        if len(text) > MAX_RESPONSE_LEN:
            await status_msg.edit_text("✅ 响应过长，已保存为文件")
            file_data = io.BytesIO(text.encode("utf-8"))
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_data,
                filename="response.txt",
                caption=f"完整回复（{len(text)} 字符）",
            )
        else:
            await status_msg.edit_text(text)

    except Exception as e:
        logger.exception("AcademicLoop error")
        try:
            await status_msg.edit_text(f"❌ 学术团队错误: {e}")
        except Exception:
            pass


async def _handle_via_tmux(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    user_text: str, chat_id: int,
):
    """Fallback: send to opencode via tmux (original behavior)."""
    before_text, before_lines = capture_pane()
    send_keys(user_text)
    status_msg = await update.message.reply_text("🤔 处理中...")

    try:
        new_output = await poll_for_output(before_text, before_lines)
        cleaned = _clean_opencode_output(new_output)
        if not cleaned:
            cleaned = new_output

        if cleaned:
            if len(cleaned) > MAX_RESPONSE_LEN:
                await status_msg.edit_text("✅ 响应过长，已保存为文件")
                file_data = io.BytesIO(cleaned.encode("utf-8"))
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=file_data,
                    filename="response.txt",
                    caption=f"完整回复（{len(cleaned)} 字符）",
                )
            else:
                await status_msg.edit_text(cleaned)
        else:
            await status_msg.edit_text("✅ 已完成（空输出）")
    except asyncio.CancelledError:
        await status_msg.edit_text("⏹️ 已取消")
    except Exception as e:
        logger.exception("Error processing message")
        try:
            await status_msg.edit_text(f"❌ 错误: {e}")
        except Exception:
            pass


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **opencode Telegram 桥接**\n\n"
        "发送任意消息给 opencode 处理\n\n"
        "命令:\n"
        "/status — 检查桥接和会话状态\n"
        "/respawn — 重启 opencode 会话\n"
        "/help — 显示此帮助\n\n"
        "提示: 一次只发一个问题，排队处理"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alive = session_alive()
    if alive:
        pane_text, pane_lines = capture_pane()
        loop_status = "可用" if academic_loop_available() else "未启动"
        await update.message.reply_text(
            f"✅ **连接正常**\n"
            f"会话: `{TMUX_SESSION}`\n"
            f"缓冲区: {pane_lines} 行\n"
            f"学术团队: {loop_status}\n"
            f"轮询: 每 {POLL_INTERVAL}s, 稳定 {STABLE_SECONDS}s 判完成\n"
            f"队列: {'⏳ 繁忙' if _msg_lock.locked() else '空闲'}"
        )
    else:
        await update.message.reply_text("❌ 会话断开, /respawn 重建")


async def cmd_respawn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if session_alive():
        await update.message.reply_text("🔄 正在重启...")
    else:
        await update.message.reply_text("🔄 正在创建新会话...")
    try:
        session_respawn()
        await asyncio.sleep(2)
        if session_alive():
            await update.message.reply_text("✅ opencode 已重启")
        else:
            await update.message.reply_text("❌ 重启失败")
    except Exception as e:
        await update.message.reply_text(f"❌ 错误: {e}")


# ── Main ────────────────────────────────────────────────────

def main():
    from telegram.request import HTTPXRequest

    _tmux(["set-option", "-g", "history-limit", str(TMUX_HISTORY_LIMIT)], timeout=3)
    if not session_alive():
        logger.info("Creating tmux session '%s'...", TMUX_SESSION)
        session_create()

    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    request_kwargs = {
        "connection_pool_size": 16,
        "read_timeout": 60.0,
        "connect_timeout": 15.0,
        "pool_timeout": 10.0,
    }
    if proxy_url:
        request_kwargs["proxy"] = proxy_url
        request_kwargs["http_version"] = "1.1"
        logger.info("Using proxy: %s", proxy_url)

    request = HTTPXRequest(**request_kwargs)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("respawn", cmd_respawn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bridge started (polling mode, proxy=%s)", bool(proxy_url))
    app.run_polling(allowed_updates=["messages"])


if __name__ == "__main__":
    main()
