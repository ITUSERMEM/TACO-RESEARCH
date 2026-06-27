#!/bin/bash
# Weekly expansion — automatically extends fault catalog and adversarial tests.
# Run: bash weekly_expansion.sh

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "Weekly Expansion - $(date)"
echo "=========================================="

echo ""
echo "=== Step 1: Expanding Fault Catalog ==="
python3 expand_fault_catalog.py --save fault_catalog_expanded.json

echo ""
echo "=== Step 2: Expanding Adversarial Tests ==="
python3 expand_adversarial_tests.py --save tests/test_adversarial_expanded.py

echo ""
echo "=== Step 3: Running New Tests ==="
if [ -f tests/test_adversarial_expanded.py ]; then
    python3 -m pytest tests/test_adversarial_expanded.py -v --tb=line || {
        echo ""
        echo "WARNING: Some new tests failed. Review before merging."
    }
else
    echo "  (no new test file generated)"
fi

echo ""
echo "=== Step 4: Monitoring Contract Violations ==="
python3 monitor_contract.py

echo ""
echo "=========================================="
echo "Done!"
echo "  Catalog:    fault_catalog_expanded.json"
echo "  Tests:      tests/test_adversarial_expanded.py"
echo "=========================================="
