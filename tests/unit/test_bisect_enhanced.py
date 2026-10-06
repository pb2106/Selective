"""
Unit tests for Advanced Bisecting Engine, Reproduction Generator, and Causal Chain Explanation.
"""

import tempfile
import json
from pathlib import Path
from selective.harness.bisect import AdvancedBisector, explain_causal_why

def test_bisector_reproduction_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "test_app.py"
        script_path.write_text("import math\nprint(math.sqrt(4))\n", encoding="utf-8")

        bisector = AdvancedBisector(str(script_path), package_name="math")
        res = bisector.bisect()

        assert res.script_path == str(script_path)
        assert isinstance(res.iterations, int)

def test_explain_causal_why():
    exp = explain_causal_why("torch.fx")
    assert exp["module"] == "torch.fx"
    assert "causal_chain" in exp
    assert len(exp["causal_chain"]) > 0
    assert "OEC L2 mismatch" in exp["causal_chain"][-1]
