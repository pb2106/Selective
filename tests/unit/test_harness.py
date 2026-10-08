"""
Unit tests for Verification Harness (OEC, Diff Engine, Bisect).
"""

import tempfile
from pathlib import Path
from selective.harness.oec import OECSnapshotEngine, OECSnapshot
from selective.analyzer.graph_builder import PackageGraph, GraphEdge
from selective.harness.bisect import EdgeBisector
from selective.harness.verify import DifferentialVerifier

def test_oec_snapshot_diffing():
    snap_a = OECSnapshot(
        l1_namespaces={"pkg": ["a", "b"]},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env": "x"},
        l5_error_timing={}
    )
    snap_b = OECSnapshot(
        l1_namespaces={"pkg": ["a", "b", "c"]},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env": "x"},
        l5_error_timing={}
    )

    diff = snap_a.diff(snap_b)
    assert "L1_Namespace" in diff
    assert "pkg" in diff["L1_Namespace"]
    assert diff["L1_Namespace"]["pkg"]["only_in_target"] == ["c"]

def test_edge_bisector():
    graph = PackageGraph("dummy")
    edge1 = GraphEdge("dummy", "dummy.a", "import", [], 1, safety_class="SAFE_LAZY")
    edge2 = GraphEdge("dummy", "dummy.b", "import", [], 2, safety_class="SAFE_LAZY")
    graph.add_edge(edge1)
    graph.add_edge(edge2)

    # Mock verify_fn that fails when edge1 is lazy
    def mock_verify():
        # returns False if edge1 is SAFE_LAZY
        return edge1.safety_class != "SAFE_LAZY"

    bisector = EdgeBisector(graph, mock_verify)
    prob, safe = bisector.bisect()

    assert len(prob) == 1
    assert prob[0] == edge1

def test_oec_selective_disable_ignored():
    snap_a = OECSnapshot(
        l1_namespaces={},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env_vars": {"SELECTIVE_DISABLE": "1", "PATH": "/bin"}},
        l5_error_timing={}
    )
    snap_b = OECSnapshot(
        l1_namespaces={},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env_vars": {"PATH": "/bin"}},
        l5_error_timing={}
    )

    diff = snap_a.diff(snap_b)
    assert "L4_ProcessState" not in diff
    assert diff == {}

def test_oec_real_env_diff_reported():
    snap_a = OECSnapshot(
        l1_namespaces={},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env_vars": {"PATH": "/bin"}},
        l5_error_timing={}
    )
    snap_b = OECSnapshot(
        l1_namespaces={},
        l2_registries={},
        l3_behavior={"status": "ok"},
        l4_process_state={"env_vars": {"PATH": "/bin", "FOO": "bar"}},
        l5_error_timing={}
    )

    diff = snap_a.diff(snap_b)
    assert "L4_ProcessState" in diff
    assert "env_vars" in diff["L4_ProcessState"]
    assert diff["L4_ProcessState"]["env_vars"]["target"].get("FOO") == "bar"

def test_differential_verifier_ignores_selective_disable(tmp_path):
    script_file = tmp_path / "dummy_script.py"
    script_file.write_text("import sys\nprint('hello')\n")
    verifier = DifferentialVerifier(str(script_file))
    res = verifier.verify()
    assert res["passed"] is True
    assert res["diffs"] == {}

def test_differential_verifier_catches_real_env_diff(tmp_path):
    script_file = tmp_path / "env_script.py"
    script_file.write_text("import os\nif os.environ.get('SELECTIVE_DISABLE') == '1':\n    os.environ['FOO'] = 'baseline'\nelse:\n    os.environ['FOO'] = 'target'\n")
    verifier = DifferentialVerifier(str(script_file))
    res = verifier.verify()
    assert res["passed"] is False
    assert "L4_ProcessState" in res["diffs"]
    assert "env_vars" in res["diffs"]["L4_ProcessState"]
    assert res["diffs"]["L4_ProcessState"]["env_vars"]["baseline"].get("FOO") == "baseline"
    assert res["diffs"]["L4_ProcessState"]["env_vars"]["target"].get("FOO") == "target"


