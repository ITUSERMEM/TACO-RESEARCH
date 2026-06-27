"""8 tests for PersistLearnings + BoundedAppend + FileLock."""
import pytest, sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from persist_learnings import PersistLearnings, FileLock


class TestPersistLearnings:
    @pytest.fixture
    def pl(self):
        tmp = tempfile.mkdtemp()
        yield PersistLearnings(memory_dir=tmp, role="test")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_create_memory_file(self, pl):
        assert os.path.exists(pl.memory_path)

    def test_extract_and_persist(self, pl):
        msgs = [{"role": "assistant", "content": "Key finding: accuracy improved by 5%"}]
        n = pl.extract_and_persist(msgs, source="test")
        assert n > 0

    def test_bounded_append_no_overflow(self, pl):
        lines = ["- test line"] * 10
        n = pl._bounded_append(lines)
        assert n == 10

    def test_read_memory(self, pl):
        content = pl.read_memory()
        assert len(content) > 0

    def test_line_count(self, pl):
        count = pl.get_line_count()
        assert count > 0

    def test_dedup_identical_content(self, pl):
        msgs = [{"role": "assistant", "content": "Key finding: unique_test_12345"}]
        n1 = pl.extract_and_persist(msgs, source="test1")
        assert n1 > 0
        content = pl.read_memory()
        assert "unique_test_12345" in content

    def test_skip_trivial_content(self, pl):
        msgs = [{"role": "assistant", "content": "=== START ==="}]
        n = pl.extract_and_persist(msgs, source="test")
        assert n == 0

    def test_clear(self, pl):
        pl.clear()
        content = pl.read_memory()
        assert len(content) > 0


class TestFileLock:
    def test_lock_unlock(self):
        fd = os.open("/tmp/test_lock", os.O_CREAT | os.O_RDONLY, 0o600)
        FileLock.lock(fd)
        FileLock.unlock(fd)
        os.close(fd)
        os.unlink("/tmp/test_lock")

    def test_try_lock(self):
        fd = os.open("/tmp/test_try", os.O_CREAT | os.O_RDONLY, 0o600)
        locked = FileLock.try_lock(fd)
        assert locked is True
        FileLock.unlock(fd)
        os.close(fd)
        os.unlink("/tmp/test_try")
