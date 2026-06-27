"""8 tests for Scheduler (cron matching + schedule lifecycle)."""
import pytest, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scheduler import SimpleCronMatcher, AcademicScheduler, ScheduleEntry


class TestCronMatcher:
    def test_every_minute(self):
        assert SimpleCronMatcher.match("* * * * *") is True

    def test_specific_minute(self):
        now = time.localtime()
        expr = f"{now.tm_min} * * * *"
        assert SimpleCronMatcher.match(expr) is True

    def test_wrong_minute(self):
        expr = "99 * * * *"
        assert SimpleCronMatcher.match(expr) is False

    def test_step_pattern(self):
        now = time.localtime()
        if now.tm_min % 5 == 0:
            assert SimpleCronMatcher.match("*/5 * * * *") is True

    def test_list_pattern(self):
        assert SimpleCronMatcher._match_field("0,15,30,45", 15) is True

    def test_range_pattern(self):
        assert SimpleCronMatcher._match_field("9-17", 12) is True

    def test_outside_range(self):
        assert SimpleCronMatcher._match_field("9-17", 20) is False

    def test_invalid_expr(self):
        assert SimpleCronMatcher.match("invalid") is False


class TestAcademicScheduler:
    @pytest.fixture
    def sched(self):
        import tempfile
        import random, string
        name = "test_" + ''.join(random.choices(string.ascii_lowercase, k=8)) + ".json"
        path = os.path.join(tempfile.gettempdir(), name)
        s = AcademicScheduler(schedules_file=path)
        yield s
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def test_default_tasks_loaded(self, sched):
        assert len(sched.all()) >= 3

    def test_add_schedule(self, sched):
        entry = ScheduleEntry(id="test1", cron="0 0 * * *", agent="test", prompt="test")
        sched.add(entry)
        assert sched.get("test1") is not None

    def test_remove_schedule(self, sched):
        entry = ScheduleEntry(id="test2", cron="0 0 * * *", agent="test", prompt="test")
        sched.add(entry)
        assert sched.remove("test2") is True
        assert sched.get("test2") is None

    def test_start_stop(self, sched):
        sched.start()
        sched.stop()
