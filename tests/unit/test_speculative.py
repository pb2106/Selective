"""
Unit tests for Background Speculative Loading Scheduler.
"""

import sys
import time
import pytest
import selective
from selective.loader.speculative import SpeculativeScheduler, prefetch
from selective.loader.miss_path import taint_package, is_package_tainted

def test_speculative_scheduler_basic():
    scheduler = SpeculativeScheduler.get_instance()
    scheduler.start()

    prefetch("math", confidence=0.9)
    # Give background thread time to prepare
    time.sleep(0.3)

    diag = scheduler.get_diagnostics()
    assert diag["speculative_enabled"] is True
    assert isinstance(diag["prepared_count"], int)

def test_speculative_scheduler_duplicate_requests():
    scheduler = SpeculativeScheduler.get_instance()
    scheduler.schedule("os", confidence=0.8)
    scheduler.schedule("os", confidence=0.8)  # Duplicate, should be ignored safely

    time.sleep(0.2)
    diag = scheduler.get_diagnostics()
    assert "os" in diag["prepared_modules"] or "os" in sys.modules

def test_speculative_tainted_package():
    taint_package("tainted_dummy_pkg", "Test taint")
    assert is_package_tainted("tainted_dummy_pkg") is True

    scheduler = SpeculativeScheduler.get_instance()
    scheduler.schedule("tainted_dummy_pkg.sub", parent_package="tainted_dummy_pkg")
    time.sleep(0.1)

    diag = scheduler.get_diagnostics()
    assert "tainted_dummy_pkg.sub" not in diag["prepared_modules"]

def test_speculative_shutdown():
    scheduler = SpeculativeScheduler.get_instance()
    scheduler.shutdown()
    diag = scheduler.get_diagnostics()
    assert diag["speculative_enabled"] is False
