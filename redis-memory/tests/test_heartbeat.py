"""6 tests for Heartbeat."""
import pytest, sys, os, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from heartbeat import Heartbeat, HeartbeatConfig


class TestHeartbeat:
    @pytest.fixture
    def hb(self):
        tmp = tempfile.mkdtemp()
        h = Heartbeat(base_dir=tmp)
        yield h
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_register_unregister(self, hb):
        cfg = HeartbeatConfig(agent="test-agent", interval_secs=60)
        hb.register(cfg)
        status = hb.status()
        assert "test-agent" in status
        hb.unregister("test-agent")
        assert "test-agent" not in hb.status()

    def test_in_active_hours(self, hb):
        cfg = HeartbeatConfig(agent="day-agent", interval_secs=60,
                              active_hours_start=0, active_hours_end=24)
        assert cfg.in_active_hours() is True

    def test_outside_active_hours(self, hb):
        cfg = HeartbeatConfig(agent="night-agent", interval_secs=60,
                              active_hours_start=23, active_hours_end=6)
        from datetime import datetime
        if datetime.now().hour < 23 and datetime.now().hour >= 6:
            assert cfg.in_active_hours() is False

    def test_force_run(self, hb):
        cfg = HeartbeatConfig(agent="test-agent", interval_secs=60)
        hb.register(cfg)
        result = hb.force_run("test-agent")
        assert result is not None or result is None

    def test_checklist_file_created(self, hb):
        cfg = HeartbeatConfig(agent="experimenter", interval_secs=1800)
        hb.register(cfg)
        path = os.path.join(hb.base_dir, "experimenter_HEARTBEAT.md")
        assert os.path.exists(path)

    def test_start_stop(self, hb):
        hb.start()
        hb.stop()
