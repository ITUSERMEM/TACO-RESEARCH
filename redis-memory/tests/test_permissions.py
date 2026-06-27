"""15 tests for 7-level permission system."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from permissions import PermissionSystem


class TestPermissions:
    def setup_method(self):
        self.p = PermissionSystem()

    def test_hard_blocked_rm_rf(self):
        r = self.p.check_bash("rm -rf /")
        assert r.allowed is False

    def test_hard_blocked_dd(self):
        r = self.p.check_bash("dd if=/dev/sda of=/dev/null")
        assert r.allowed is False

    def test_safe_ls(self):
        r = self.p.check_bash("ls")
        assert r.allowed is True

    def test_always_ask_python_c(self):
        r = self.p.check_bash("python -c 'print(1)'")
        assert r.requires_approval is True

    def test_sensitive_env_file(self):
        r = self.p.check_file_read("/home/user/.env")
        assert r.requires_approval is True

    def test_sensitive_ssh_key(self):
        r = self.p.check_file_read("/home/user/.ssh/id_rsa")
        assert r.requires_approval is True

    def test_allowed_dir_file(self):
        self.p.add_allowed_dir("/home/user/project")
        r = self.p.check_file_read("/home/user/project/data.csv")
        assert r.allowed is True

    def test_outside_allowed_dir(self):
        self.p.allowed_dirs = ["/home/user"]
        r = self.p.check_file_read("/etc/passwd")
        assert r.allowed is False

    def test_network_whitelist(self):
        self.p.add_network_allowed("api.deepseek.com")
        r = self.p.check_network("https://api.deepseek.com/v1/chat")
        assert r.allowed is True

    def test_network_blocked(self):
        r = self.p.check_network("https://evil.com/steal")
        assert r.allowed is False

    def test_compound_and(self):
        r = self.p.check_bash("ls && rm -rf /")
        assert r.allowed is False

    def test_compound_pipe(self):
        r = self.p.check_bash("cat data.csv | grep test")
        assert r.allowed is True

    def test_empty_command(self):
        r = self.p.check_bash("")
        assert r.allowed is True

    def test_allow_after_add_whitelist(self):
        self.p.add_network_allowed("example.com")
        r = self.p.check_network("https://example.com/api")
        assert r.allowed is True

    def test_localhost_always_allowed(self):
        r = self.p.check_network("http://127.0.0.1:6379")
        assert r.allowed is True
