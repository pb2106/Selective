"""
Unit tests for PackageGraph and Serializer.
"""

import tempfile
from pathlib import Path
from selective.analyzer.graph_builder import PackageGraph, GraphNode, GraphEdge
from selective.analyzer.serializer import GraphSerializer

def test_graph_serialization_roundtrip():
    graph = PackageGraph("dummy_pkg", package_hash="abc123hash")
    node_a = GraphNode("dummy_pkg", "/path/__init__.py", is_init=True, symbols_defined=["foo"])
    node_b = GraphNode("dummy_pkg.sub", "/path/sub.py", is_init=False, symbols_defined=["bar"])
    
    edge = GraphEdge("dummy_pkg", "dummy_pkg.sub", "import", [("sub", None)], line_number=1, safety_class="SAFE_LAZY", evidence_tier=1)

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_edge(edge)
    graph.add_eliminated_edge("dummy_pkg", "typing", "TYPE_CHECKING block", 2)

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "graph.json"
        bin_path = Path(tmpdir) / "graph.bin"

        # Test JSON
        GraphSerializer.save_json(graph, json_path)
        restored_json = GraphSerializer.load_json(json_path)
        assert restored_json.package_name == "dummy_pkg"
        assert len(restored_json.nodes) == 2
        assert len(restored_json.edges) == 1
        assert restored_json.edges[0].safety_class == "SAFE_LAZY"

        # Test Binary
        GraphSerializer.save_binary(graph, bin_path)
        restored_bin = GraphSerializer.load_binary(bin_path)
        assert restored_bin.package_name == "dummy_pkg"
        assert len(restored_bin.nodes) == 2
        assert len(restored_bin.edges) == 1
        assert restored_bin.edges[0].safety_class == "SAFE_LAZY"
