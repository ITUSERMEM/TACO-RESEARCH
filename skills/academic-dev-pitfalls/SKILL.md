---
name: academic-dev-pitfalls
description: Academic Team 开发踩坑清单。每次改动 academic team 代码前必须加载此 skill。列出 45 个已验证的 Bug 模式及对应约束，按类别分为基础设施/Telegram 桥接/编排器/模块编码/测试/安全六章。
trigger: 当用户要对 academic team（redis-memory/ 或 telegram_bridge/）做任何代码修改、新增功能、修复 bug 时，必须先加载本 skill 并逐一检查每类约束。
---

# Academic Team 开发约束清单

从 P0 到测试全流程踩过的 **45 个已验证 Bug**，分为六类。每次改代码前必须逐项检查。

---

## 一、基础设施（6 项）

### 1.1 Redis 持久化
```
❌ 错误：docker run redis-stack 不加 -v，不开 AOF
✅ 正确：docker run -v /data/redis-stack:/var/lib/redis-stack \
         --restart=unless-stopped \
         redis/redis-stack-server:latest redis-stack-server --appendonly yes
```
- `systemd` + `AOF` + `volume` 三件套必配

### 1.2 systemd 服务
```
❌ 错误：Python path 用 /usr/bin/python3
✅ 正确：ExecStart=/root/anaconda3/bin/python3 ...
```
- `Type=simple; Restart=always; RestartSec=5`
- Python 路径用 `/root/anaconda3/bin/python3`
- 环境变量用 `Environment=` 显式设置

### 1.3 tmux 命令容错
```
❌ 错误：ExecStartPre=/usr/bin/tmux kill-session -t opencode || true
         （systemd 不支持 ||，且 - 前缀才忽略错误）
✅ 正确：ExecStartPre=-/usr/bin/tmux kill-session -t opencode
```

### 1.4 进程管理
```
❌ 错误：8 个 opencode 进程并行运行，内存耗尽
✅ 正确：每个 session 只保留 1 个 opencode 进程，定时清理僵尸
```

---

## 二、Telegram 桥接（14 项）

### 2.1 全局变量
```
❌ 错误：global _capture_count 未初始化
         → NameError: name '_capture_count' is not defined
✅ 正确：删除无用全局变量声明，或显式初始化 = 0
```

### 2.2 输出提取算法
```
❌ 错误 1：集合差集 set(a_lines) - set(b_lines)
         → 丢失重复行、丢失顺序、错位
✅ 正确 1：前缀偏移 a_lines[len(b_lines):]

❌ 错误 2：后缀重叠从底向上找差异
         → 只拿到 UI 边框，正文为空
✅ 正确 2：从顶向下找第一个不同行
         for i in range(min(len(a), len(b))):
             if a[i] != b[i]:
                 return a[i:]
```

### 2.3 终端限制
```
❌ 错误：pane 高度 40 行，长回复被截
✅ 正确：tmux new-session -y 120 设置 120 行
         capture-pane -S -200 取最后 200 行
         超 3800 字符 → send_document 发文件
```

### 2.4 pipe-pane 陷阱
```
❌ 错误：用 pipe-pane 捕获原始字节流
         → 含全部 ANSI 重绘序列，信噪比 1%
         → 需要完整终端仿真器，工作量过大
✅ 正确：始终用 capture-pane 读已渲染终端状态
```

### 2.5 截断方向
```
❌ 错误：cleaned[:3800] 从开头切 → 丢正文尾部
✅ 正确：cleaned[-3780:] 保尾，前加 "…(前文已截断)"
```

### 2.6 稳定性检测
```
❌ 错误：对比整页内容，状态栏计时器永远在变
         → 永远判不稳 → 超时取空结果
✅ 正确：_strip_bottom(content, 3) 排除底栏再比较
         ANIMATED_PATTERNS 过滤 Build · / ctrl+p 等动画行
```

### 2.7 消息路由
```
❌ 错误：academic_loop_available() 只看订阅数不看是否可用
         → daemon 有订阅但 process_incoming 不干活
         → 桥接等 120s 超时
✅ 正确：加 LOOP_ENABLED 开关，默认 False
         确认 daemon 能处理后再切 True
```

### 2.8 pipeline_ack 处理
```
❌ 错误：收到 pipeline_ack 就 break → 不 listening 进度
✅ 正确：
    if msg_type == "pipeline_ack":
        edit_text("管线运行中...")
        continue  # 继续监听 progress + result
    if msg_type == "pipeline_result":
        response = data
        break   # 只有结果才退出
```

### 2.9 进度消息策略
```
❌ 错误：所有消息都用 edit_text → 覆盖看不到历史
✅ 正确：
    - status_msg (edit_text): 仅 % + Phase 标签
    - reply_text: Agent 启动/完成、skill 输出、关键事件
```

### 2.10 HTTPX 代理参数
```
❌ 错误：proxy_url 参数（PTB v20 旧 API）
         → TypeError: HTTPXRequest got unexpected keyword 'proxy_url'
✅ 正确：inspect.signature(HTTPXRequest.__init__) 确认参数名
          PTB v22 用 proxy 而非 proxy_url
         {
             "proxy": "http://127.0.0.1:7892",
             "read_timeout": 60.0,
             "connect_timeout": 15.0,
             "http_version": "1.1"
         }
```

### 2.11 长轮询超时
```
❌ 错误：read_timeout=30 → Telegram 长轮询被 proxy 中断
         → EndOfStream
✅ 正确：read_timeout=60, http_version="1.1"
```

---

## 三、编排器（9 项）

### 3.1 Agent 迭代必须调用 skill
```
❌ 错误：_execute_agent_iteration() 空转 LLM
         prompt → LLM response → 记录，无工具调用
✅ 正确：三步循环
    1. suggest_skill(role, task, llm) → 选 skill
    2. run_skill(name, args, progress_callback) → 执行
    3. skill 结果回注 LLM 上下文 → LLM 消化产出
```

### 3.2 process_incoming 必须启动管线
```
❌ 错误：只记录消息到 LTM，不跑 run()
✅ 正确：threading.Thread(target=_run_pipeline, daemon=True).start()
```

### 3.3 管线默认全流程
```
❌ 错误：run(start_phase=Phase0, end_phase=Phase.PHASE1) 硬编码
✅ 正确：默认 run(Phase0, Phase.PHASE5)
```

### 3.4 命令路由
```
❌ 错误：所有消息都启动管线
         → "结果怎么样" 也启动新管线
✅ 正确：路由表
    /status   → 返回 PhaseTracker 状态
    /results  → 返回上次结果
    /stop     → 停止当前管线
    /research → 启动管线（仅 idle 时）
    普通文本   →  idle 时启动，running 时提示
```

### 3.5 闭包 import
```
❌ 错误：closure 中用 sys.stdout 但没 import sys
         → NameError in thread
✅ 正确：模块顶部 import sys，或闭包内 import
```

### 3.6 陈旧状态清理
```
❌ 错误：PhaseTracker 状态 persist 在 Redis
         重启后 status=running 残留在那里
         新消息被"管线正在运行中"阻止
✅ 正确：daemon 启动时 _clear_stale_state()
         >10min 的 running 自动重置为 idle
         process_incoming 检查 >30min 自动清理
```

### 3.7 进度推送可靠性
```
❌ 错误：emit_progress → Redis publish
         但 bridge 可能在 restart 后未重新 subscribe
✅ 正确：progress 和 outbox 用同一个 pubsub 连接
         bridge 中 subscribe(outbox, progress) 同时订阅
```

### 3.8 LTM topics 不可为空
```
❌ 错误：create_long_term_memory 不传 topics
         → 搜索 topics=["review-audit"] 返回空
✅ 正确：每次 persist 必传 topics=["phase-complete", f"phase-{phase}", project_id]
```

---

## 四、模块编码（9 项）

### 4.1 属性名不要覆盖方法名
```
❌ 错误：
    class X:
        def __init__(self, assert_clean):
            self.assert_clean = assert_clean  # ← 覆盖同名方法
        def assert_clean(self): ...
    → TypeError: 'bool' object is not callable

✅ 正确：
    self._assert_clean_enabled = assert_clean
```

### 4.2 文件锁必须先创建文件
```
❌ 错误：os.open(lock_path, O_RDONLY)
         → FileNotFoundError: lock 文件不存在
✅ 正确：
    if not os.path.exists(lock_path):
        with open(lock_path, "w") as f: f.write("")
    fd = os.open(lock_path, O_RDONLY)
```

### 4.3 正则表达式硬阻断
```
❌ 错误：\brm\s+-rf\s+/\b 不匹配 "rm -rf /"
✅ 正确：(^|\s)rm\s+-rf\s+/
```

### 4.4 复合命令空格
```
❌ 错误：cmd = " rm -rf /".strip() 后直接匹配
         → 白名单前缀 "rm -rf /" 不匹配 "rm -rf /"
✅ 正确：cmd = re.sub(r'\s+', ' ', cmd.strip())
```

### 4.5 拒绝后成功检测
```
❌ 错误：rf"I (succeeded|completed) (the )?{tool}"
         → "I successfully completed the {tool}" 不匹配
✅ 正确：rf"I .*(succeeded|completed).*{re.escape(tool)}"
```

### 4.6 subprocess shell 参数
```
❌ 错误：f"opencode run /{name} {args}"
         → args="Execute Phase 0 (环境初始化)" 括号被 shell 解释
         → Syntax error: "(" unexpected
✅ 正确：safe_args = shlex.quote(args[:300])
         cmd = f"opencode run /{name} {safe_args}"
```

### 4.7 subprocess 逐行读取
```
❌ 错误：subprocess.run(cmd, capture_output=True)
         → skill 是交互式的，卡住
✅ 正确：Popen(cmd, stdout=PIPE, bufsize=1)
         for line in proc.stdout:
             if progress_callback:
                 progress_callback(line)
```

### 4.8 类内外缩进
```
❌ 错误：在 class 内插入了 module-level 函数
         → 后续所有方法被"挤出"类外
         → AttributeError: _ensure_loaded not found
✅ 正确：缩进严格对齐，class 内 4 空格，外 0 空格
         用编辑器的高亮确认每个方法在 class 下方
```

### 4.9 pytest 与 __init__.py
```
❌ 错误：测试目录上一级的 __init__.py 含相对 import
         → pytest import 时触发 from .agent_memory import ...
         → ImportError: attempted relative import with no known parent package
✅ 正确：测试目录不依赖 __init__.py
         或 --import-mode=append 跳过相对 import
```

---

## 五、测试（4 项）

### 5.1 改完必跑回归
```
❌ 错误：修一个 bug 不跑测试 → 引入新 bug
✅ 正确：每次代码修改后：
    cd /root/.config/opencode/redis-memory
    python3 -m pytest tests/ -v --tb=short
    目标：128/128 全部通过
```

### 5.2 先写测试再改代码
```
❌ 错误：先改代码再手动 Telegram 测试 → 效率极低
✅ 正确：核心逻辑先写 pytest 再实现
```

### 5.3 测试隔离
```
❌ 错误：pytest 直接连接生产 Redis
         → 测试 flushdb 清掉研发数据
✅ 正确：测试用独立 Redis DB (db=1) 或用 mock
```

### 5.4 subprocess 必须 mock
```
❌ 错误：test_skill_executor 没 mock subprocess
         → 每次测试真的调用 opencode，慢且依赖 CLI 存在
✅ 正确：mocker.patch("subprocess.Popen", return_value=mock_proc)
```

---

## 六、安全（3 项）

### 6.1 API Key 硬编码
```
❌ 错误：PRO_API_KEY = "sk-2048cbfa8fa043..."
         → 提交即泄露
✅ 正确：PRO_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
         无 fallback 值
```

### 6.2 Token 文件权限
```
❌ 错误：bot_token.txt 权限 644，任意进程可读
✅ 正确：chmod 600 bot_token.txt
         优先用 systemd Environment=TELEGRAM_BOT_TOKEN=...
```

### 6.3 systemd 安全加固
```
✅ 加：
    [Service]
    ProtectHome=yes
    PrivateTmp=yes
    NoNewPrivileges=yes
```

---

## 开发前检查清单

每次改 `redis-memory/` 或 `telegram_bridge/` 前，逐项确认：

```
[ ] 1. 加了新的全局变量？→ 确认已初始化
[ ] 2. 改了提取算法？→ 用前缀偏移，不用集合差集
[ ] 3. 改了消息路由？→ 确认 pipeline_ack 不 break
[ ] 4. 加了 API 请求？→ 确认 timeout 设对
[ ] 5. 改了 subprocess？→ 确认 shlex.quote 和 Popen 逐行
[ ] 6. 加了新的实例属性？→ 确认不与方法重名
[ ] 7. 改了缩进？→ 确认 class 内外层次
[ ] 8. 加了新的存储？→ 确认 topics 参数
[ ] 9. 改了 systemd？→ 确认 Python 路径、- 前缀、Restart
[ ] 10. 改了测试？→ 确认不用生产 Redis、mock subprocess
[ ] 11. 改完跑 pytest？→ redis-memory 下 python3 -m pytest tests/
[ ] 12. 改了 Telegram 交互？→ 确认 proxy、timeout、http_version
[ ] 13. 加了新的 API key？→ 确认 env var 无 fallback
[ ] 14. pipeline 状态？→ 确认了 stale 清理逻辑
[ ] 15. 改了进程管理？→ 确认了 zombie 清理
```
