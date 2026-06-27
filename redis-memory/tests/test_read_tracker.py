"""6 tests for ReadTracker."""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from read_tracker import ReadTracker


class TestReadTracker:
    def test_record_and_dedup(self):
        rt = ReadTracker()
        rt.record_read("paper.pdf", mtime=1000, size=500)
        result = rt.check_dedup("paper.pdf", mtime=1000, size=500)
        assert result is not None
        assert "Unchanged" in result

    def test_changed_file_no_dedup(self):
        rt = ReadTracker()
        rt.record_read("paper.pdf", mtime=1000, size=500)
        result = rt.check_dedup("paper.pdf", mtime=1001, size=500)
        assert result is None

    def test_read_before_write_blocked(self):
        rt = ReadTracker()
        result = rt.check_read_before_write("data.csv")
        assert result is not None
        assert "blocked" in result

    def test_read_before_write_allowed(self):
        rt = ReadTracker()
        rt.record_read("data.csv")
        result = rt.check_read_before_write("data.csv")
        assert result is None

    def test_cross_role_dedup(self):
        rt = ReadTracker()
        rt.mark_role_done("literature_researcher", "search:attention")
        assert rt.is_role_done("literature_researcher", "search:attention") is True
        assert rt.is_role_done("literature_researcher", "search:transformer") is False

    def test_open_tasks(self):
        rt = ReadTracker()
        rt.mark_role_done("experimenter", "task_a")
        open_tasks = rt.get_open_tasks(["task_a", "task_b", "task_c"], "experimenter")
        assert open_tasks == ["task_b", "task_c"]
