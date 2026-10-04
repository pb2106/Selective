"""
Unit tests for Verification Harness (OEC, Diff Engine, Bisect).
"""

import tempfile
from pathlib import Path
from selective.harness.oec import OECSnapshotEngine, OECSnapshot
from selective.analyzer.graph_builder import PackageGraph, GraphEdge
from selective.harness.bisect import EdgeBisector

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
