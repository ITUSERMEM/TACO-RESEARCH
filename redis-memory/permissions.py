"""Permissions — Kocoro-inspired 7-level permission system.

Provides fine-grained access control for academic team tools:
- Hard-blocked commands (rm -rf /, dd if=...)
- Denied commands (user-configured)
- Always-ask prefixes (high-risk operations)
- Allowed commands (user-configured)  
- Default-safe commands (read-only built-in whitelist)
- Compound command splitting (&&, ||, ;, |)
- File path checking against allowed directories
- Network egress against allowlist
"""

import os
import re
import shlex
from typing import Optional

# Hard-blocked patterns (always deny, regardless of config)
HARD_BLOCKED_RE = [
    re.compile(r"(^|\s)rm\s+-rf\s+/"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bfdisk\b"),
    re.compile(r"\bmkswap\b"),
    re.compile(r"curl\s+.*\|\s*(sh|bash|zsh)"),
    re.compile(r"wget\s+.*-O-\s*\|\s*(sh|bash|zsh)"),
    re.compile(r">\s*/dev/(sda|sdb|sdc|nvme|mmc)"),
    re.compile(r":\(\)\{\s*:\s*\|:\s*&\s*\};:"),  # fork bomb
]

# Always-ask prefixes (high risk)
ALWAYS_ASK_PREFIXES = [
    "python -c", "python3 -c", "node -e", "bash -c", "sh -c",
    "pip install", "pip3 install", "npm install", "yarn add",
    "rm -rf", "rm -r", "chmod 777", "chmod -R", "sudo",
    "apt install", "apt-get install", "yum install",
    "curl", "wget", "git push", "git merge", "git rebase",
    "docker run", "docker exec", "docker build",
    "kubectl delete", "kubectl apply",
]

# Default-safe commands (read/query only)
DEFAULT_SAFE = {
    "ls", "pwd", "echo", "cat", "head", "tail", "less", "more",
    "grep", "rg", "ag", "find", "locate", "which", "whereis",
    "date", "cal", "whoami", "id", "uname", "hostname",
    "ps", "top", "htop", "df", "du", "free", "uptime",
    "git status", "git log", "git diff", "git show", "git branch",
    "git stash list", "git remote -v", "git config",
    "docker ps", "docker images", "docker stats", "docker logs",
    "kubectl get", "kubectl describe", "kubectl logs",
    "pip list", "pip show", "pip freeze",
    "conda list", "conda info", "conda env list",
    "nvtop", "nvidia-smi", "gpustat",
    "tmux list-sessions", "tmux list-windows", "tmux list-panes",
    "redis-cli", "sqlite3", "python3 --version",
    "make --version", "cmake --version", "gcc --version",
    "curl --version", "wget --version",
    "pip install --dry-run",
    "apt list", "apt-cache search", "apt-cache show",
}

# Priority: prefix depth (how many tokens to consider when matching)
PREFIX_DEPTH = {
    "git": 2, "docker": 2, "kubectl": 2, "pip": 2, "npm": 2,
    "apt": 2, "apt-get": 2, "conda": 2, "tmux": 2,
}

# Sensitive file patterns
SENSITIVE_FILES = re.compile(r"(\.env|\.pem|\.key|id_rsa|id_dsa|\.token|secret|credential)", re.IGNORECASE)


class PermissionResult:
    def __init__(self, allowed: bool, reason: str = "", requires_approval: bool = False):
        self.allowed = allowed
        self.reason = reason
        self.requires_approval = requires_approval


class PermissionSystem:
    """7-level permission checker for academic team tool calls.

    Integrates with the tool execution pipeline to gate:
    - bash commands (command-level parsing)
    - file reads (path + sensitive file)
    - network calls (egress allowlist)
    """

    def __init__(self):
        self.denied_commands: list[str] = []
        self.allowed_commands: list[str] = []
        self.allowed_dirs: list[str] = [os.path.expanduser("~")]
        self.network_allowlist: list[str] = ["localhost", "127.0.0.1",
                                              "api.deepseek.com", "opencode.ai"]

    def check_tool(self, tool_name: str, args: dict) -> PermissionResult:
        if tool_name == "bash":
            return self.check_bash(args.get("command", ""))
        elif tool_name == "file_read":
            return self.check_file_read(args.get("path", ""))
        elif tool_name == "http":
            return self.check_network(args.get("url", ""))
        return PermissionResult(True)

    def check_bash(self, command: str) -> PermissionResult:
        if not command.strip():
            return PermissionResult(True)

        for pattern in HARD_BLOCKED_RE:
            if pattern.search(command):
                return PermissionResult(False, f"Hard-blocked command: {command[:80]}")

        sub_commands = self._split_compound(command)
        for sub in sub_commands:
            result = self._check_single_command(sub)
            if not result.allowed or result.requires_approval:
                return result

        return PermissionResult(True)

    def check_file_read(self, path: str) -> PermissionResult:
        if not path:
            return PermissionResult(True)

        abs_path = os.path.abspath(os.path.expanduser(path))

        if SENSITIVE_FILES.search(abs_path):
            return PermissionResult(False, f"Sensitive file access denied: {path}",
                                    requires_approval=True)

        for d in self.allowed_dirs:
            allowed_abs = os.path.abspath(os.path.expanduser(d))
            if abs_path.startswith(allowed_abs):
                break
        else:
            return PermissionResult(False, f"Path not in allowed directories: {path}")

        return PermissionResult(True)

    def check_network(self, url: str) -> PermissionResult:
        if not url:
            return PermissionResult(True)

        import urllib.parse
        host = urllib.parse.urlparse(url).hostname or ""

        for allowed in self.network_allowlist:
            if allowed.startswith("*.") and host.endswith(allowed[1:]):
                return PermissionResult(True)
            if host == allowed:
                return PermissionResult(True)

        return PermissionResult(False, f"Network egress not allowed: {host}",
                                requires_approval=True)

    def _check_single_command(self, cmd: str) -> PermissionResult:
        cmd = cmd.strip()
        cmd = re.sub(r'\s+', ' ', cmd)
        if not cmd:
            return PermissionResult(True)

        if cmd in self.denied_commands:
            return PermissionResult(False, f"Denied command: {cmd}")

        if cmd in self.allowed_commands:
            return PermissionResult(True)

        tokens = shlex.split(cmd)
        if not tokens:
            return PermissionResult(True)

        cmd_name = tokens[0]

        # Check always-ask prefixes
        for prefix in ALWAYS_ASK_PREFIXES:
            if cmd.startswith(prefix):
                return PermissionResult(True, requires_approval=True)

        # Check default-safe
        for safe in DEFAULT_SAFE:
            if cmd.startswith(safe):
                return PermissionResult(True)

        # Check prefix depth
        depth = PREFIX_DEPTH.get(cmd_name, 1)
        prefix = " ".join(tokens[:depth])
        if prefix in self.allowed_commands:
            return PermissionResult(True)
        if prefix in self.denied_commands:
            return PermissionResult(False, f"Denied command: {prefix}")

        # Default: safe for read-only tools, require approval for write
        if self._is_read_likely(cmd_name):
            return PermissionResult(True)

        return PermissionResult(True, requires_approval=True)

    @staticmethod
    def _split_compound(command: str) -> list[str]:
        """Split compound bash commands (&&, ||, ;, |) into sub-commands."""
        command = re.sub(r"\([^)]*\)", " ", command)  # remove (subshells)
        for sep in [" && ", " || ", " ; ", " | ", "\n"]:
            parts = command.split(sep)
            if len(parts) > 1:
                result = []
                for p in parts:
                    result.extend(PermissionSystem._split_compound(p))
                return result
        return [command] if command.strip() else []

    @staticmethod
    def _is_read_likely(cmd_name: str) -> bool:
        read_verbs = {"ls", "cat", "head", "tail", "grep", "find", "echo",
                      "pwd", "which", "stat", "file", "wc", "sort", "uniq"}
        return cmd_name in read_verbs or cmd_name in DEFAULT_SAFE

    def add_allowed_dir(self, directory: str):
        self.allowed_dirs.append(os.path.abspath(os.path.expanduser(directory)))

    def add_network_allowed(self, host: str):
        self.network_allowlist.append(host)
