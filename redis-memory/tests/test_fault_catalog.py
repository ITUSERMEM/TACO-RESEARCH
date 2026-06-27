"""Tests for fault_catalog.py — Fault pattern catalog."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestFaultCatalog:
    def test_builtin_patterns_loaded(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        assert len(catalog.get_all()) > 20

    def test_get_by_priority_critical(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        critical = catalog.get_critical()
        assert len(critical) >= 3
        for p in critical:
            assert p["priority"] == "critical"

    def test_get_by_dimension(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        ib = catalog.get_by_dimension("input_boundary")
        assert len(ib) >= 3
        for p in ib:
            assert p["dimension"] == "input_boundary"

    def test_get_by_id(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        p = catalog.get_by_id("IB-001")
        assert p is not None
        assert p["name"] == "超长上下文截断丢失关键信息"

    def test_get_by_id_not_found(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        assert catalog.get_by_id("NONEXISTENT") is None

    def test_summary(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        s = catalog.summary()
        assert s["total"] > 20
        assert "by_dimension" in s
        assert "by_priority" in s
        assert "input_boundary" in s["by_dimension"]

    def test_add_pattern(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        before = len(catalog.get_all())
        catalog.add_pattern({
            "id": "TEST-001",
            "dimension": "input_boundary",
            "name": "test pattern",
            "priority": "low",
        })
        assert len(catalog.get_all()) == before + 1

    def test_add_pattern_auto_id(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        catalog.add_pattern({"dimension": "test", "name": "auto"})
        last = catalog.get_all()[-1]
        assert last["id"].startswith("GEN-")

    def test_save_and_load(self):
        from fault_catalog import FaultCatalog
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            catalog = FaultCatalog()
            catalog.save(path)
            loaded = FaultCatalog.load(path)
            assert len(loaded.get_all()) == len(catalog.get_all())
        finally:
            os.unlink(path)

    def test_load_nonexistent(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog.load("/nonexistent/path.json")
        assert len(catalog.get_all()) > 0

    def test_all_patterns_have_required_fields(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        required = {"id", "dimension", "name", "trigger", "priority"}
        for p in catalog.get_all():
            for field in required:
                assert field in p, f"Pattern {p.get('id')} missing {field}"

    def test_all_dimensions_valid(self):
        from fault_catalog import FaultCatalog, FAULT_DIMENSIONS
        catalog = FaultCatalog()
        for p in catalog.get_all():
            assert p["dimension"] in FAULT_DIMENSIONS, f"Invalid dimension: {p['dimension']}"

    def test_all_priorities_valid(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        valid = {"critical", "high", "medium", "low"}
        for p in catalog.get_all():
            assert p["priority"] in valid, f"Invalid priority: {p['priority']}"

    def test_parse_patterns_valid_json(self):
        from fault_catalog import FaultCatalog
        response = '[{"id": "NEW-001", "dimension": "test", "name": "new"}]'
        result = FaultCatalog._parse_patterns(response)
        assert len(result) == 1
        assert result[0]["id"] == "NEW-001"

    def test_parse_patterns_invalid_json(self):
        from fault_catalog import FaultCatalog
        assert FaultCatalog._parse_patterns("not json") == []

    def test_parse_patterns_non_list(self):
        from fault_catalog import FaultCatalog
        assert FaultCatalog._parse_patterns('{"not": "list"}') == []

    def test_five_dimensions_covered(self):
        from fault_catalog import FaultCatalog
        catalog = FaultCatalog()
        dims = set(p["dimension"] for p in catalog.get_all())
        assert len(dims) == 5
