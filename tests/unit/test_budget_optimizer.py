"""
Unit tests for Import Optimization Budget Engine.
"""

import pytest
from selective.analyzer.budget_optimizer import BudgetOptimizer, OptimizationBudget, parse_time_ms, parse_memory_mb

def test_parse_units():
    assert parse_time_ms("500ms") == 500.0
    assert parse_time_ms("1.5s") == 1500.0
    assert parse_memory_mb("300MB") == 300.0
    assert parse_memory_mb("1.2GB") == 1228.8

def test_budget_optimizer_strict_safety():
    budget = OptimizationBudget(startup_target="100ms", memory_target="200MB", safety="strict")
    optimizer = BudgetOptimizer("torch", budget)
    res = optimizer.optimize()

    assert res["budget"]["safety"] == "strict"
    assert res["metric_type"] == "estimated"
    assert "transformations" in res
    assert isinstance(res["target_satisfied"], bool)
    assert len(res["transformations"]) > 0

    # Ensure native extensions stay KEEP_EAGER
    eager_mods = [t for t in res["transformations"] if t["strategy"] == "KEEP_EAGER"]
    assert len(eager_mods) > 0
    assert "NATIVE_REQUIRED" in eager_mods[0]["reason"] or "side effects" in eager_mods[0]["reason"]
