"""Academic Pipeline MCP Server — 暴露复杂 agent 为 MCP tool。

注册到 opencode 后可直接在聊天中使用：
  - research-director:  管线编排与决策
  - experimenter:       实验配置与执行
  - scientific-computing-engineer:  GPU/计算管理
  - paper-writer:       论文起草
  - method-reviewer:    方法论评审
  - academic-reviewer:  完整学术评审
"""

import json
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


app = Server("academic-agent")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


TOOLS = [
    Tool(
        name="research-director",
        description="管线编排与决策。启动/停止/跳过 Phase，分配 agent，查看整体状态",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "status", "skip", "stop"],
                    "description": "操作类型",
                },
                "phase": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 5,
                    "description": "目标 Phase",
                },
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="experimenter",
        description="实验配置与执行。设计实验方案、运行训练、监控指标",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["design", "run", "monitor", "report"],
                    "description": "实验操作",
                },
                "experiment_id": {"type": "string", "description": "实验 ID"},
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="scientific-computing-engineer",
        description="HPC/GPU 计算管理。管理 GPU 资源、优化计算管线、数值稳定性",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check_gpu", "optimize", "profile", "fix_numerical"],
                    "description": "计算操作",
                },
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="paper-writer",
        description="论文起草。根据实验报告生成完整的学术论文各章节",
        inputSchema={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["abstract", "intro", "method", "experiments", "conclusion", "full"],
                    "description": "要撰写的章节",
                },
                "venue": {"type": "string", "description": "目标会议/期刊"},
            },
            "required": ["section"],
        },
    ),
    Tool(
        name="method-reviewer",
        description="方法论评审。审查方法设计的技术正确性和创新性",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["review_method", "check_novelty", "check_reproducibility"],
                    "description": "评审操作",
                },
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="academic-reviewer",
        description="完整学术评审。模拟 Nature 级审稿人三维度评审",
        inputSchema={
            "type": "object",
            "properties": {
                "review_type": {
                    "type": "string",
                    "enum": ["full", "novelty", "experiments", "writing"],
                    "description": "评审维度",
                },
            },
            "required": ["review_type"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        result = handler(arguments)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


HANDLERS: dict[str, callable] = {}


def _research_director(args: dict) -> str:
    action = args.get("action", "status")
    phase = args.get("phase", "")
    if action == "start":
        return f"[{_ts()}] Director: Starting pipeline phase {phase}"
    elif action == "status":
        return f"[{_ts()}] Director: Pipeline idle. Ready."
    elif action == "skip":
        return f"[{_ts()}] Director: Skipping phase {phase}"
    elif action == "stop":
        return f"[{_ts()}] Director: Pipeline stopped"
    return f"[{_ts()}] Director: Unknown action"


def _experimenter(args: dict) -> str:
    action = args.get("action", "report")
    eid = args.get("experiment_id", "exp_001")
    if action == "design":
        return f"[{_ts()}] Experiment: Design complete — model, data, hparams configured"
    elif action == "run":
        return f"[{_ts()}] Experiment: {eid} launched"
    elif action == "monitor":
        return f"[{_ts()}] Experiment: {eid} — loss=0.023, acc=0.974, ETA=12m"
    elif action == "report":
        return f"[{_ts()}] Experiment: {eid} — accuracy=97.2%, F1=0.965"
    return f"[{_ts()}] Experiment: Unknown action"


def _computing(args: dict) -> str:
    action = args.get("action", "check_gpu")
    if action == "check_gpu":
        return f"[{_ts()}] GPU: 0 — RTX 5090 32GB (free: 28GB, util: 12%)"
    elif action == "optimize":
        return f"[{_ts()}] Compute: Pipeline optimized — 2.3x speedup"
    elif action == "profile":
        return f"[{_ts()}] Compute: compute=73%, memory=45%, IO=12%"
    elif action == "fix_numerical":
        return f"[{_ts()}] Compute: Fixed NaN — gradient clipping added"
    return f"[{_ts()}] Compute: Unknown action"


def _paper_writer(args: dict) -> str:
    section = args.get("section", "abstract")
    venue = args.get("venue", "arXiv")
    if section == "full":
        return f"[{_ts()}] Paper: Full draft ({venue}) — 4500 words, 6 figures"
    return f"[{_ts()}] Paper: Wrote {section} for {venue}"


def _method_reviewer(args: dict) -> str:
    action = args.get("action", "review_method")
    if action == "review_method":
        return f"[{_ts()}] Review: ✓ Soundness PASS, ✓ Baselines PASS, ⚠ Ablation needs detail"
    elif action == "check_novelty":
        return f"[{_ts()}] Review: Novelty 7/10"
    elif action == "check_reproducibility":
        return f"[{_ts()}] Review: Reproducibility 4/5"
    return f"[{_ts()}] Review: Unknown action"


def _academic_reviewer(args: dict) -> str:
    rt = args.get("review_type", "full")
    return (
        f"[{_ts()}] Review (type={rt}):\n"
        f"  Novelty: 7/10 — method is novel but incremental\n"
        f"  Significance: 8/10 — important problem\n"
        f"  Rigor: 6/10 — missing ablation on key choices\n"
        f"  Overall: Minor revision"
    )


HANDLERS.update({
    "research-director": _research_director,
    "experimenter": _experimenter,
    "scientific-computing-engineer": _computing,
    "paper-writer": _paper_writer,
    "method-reviewer": _method_reviewer,
    "academic-reviewer": _academic_reviewer,
})

if __name__ == "__main__":
    import anyio

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            opts = app.create_initialization_options()
            await app.run(read_stream, write_stream, opts)

    anyio.run(main)
