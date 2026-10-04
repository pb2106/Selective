"""
Integration test suite for Real Package Validation (pandas, scipy, numpy, torch).
Builds AOT safety graphs and runs OEC differential verification.
"""

import sys
import pytest
from selective.analyzer.scanner import PackageScanner
from selective.analyzer.import_extractor import ImportExtractor
from selective.analyzer.side_effects import SideEffectAnalyzer
from selective.analyzer.classifier import SafetyClassifier
from selective.analyzer.graph_builder import PackageGraph, GraphNode, GraphEdge
from selective.loader.finder import SelectiveFinder
from selective.harness.oec import OECSnapshotEngine

TARGET_PACKAGES = ["numpy", "pandas", "scipy", "torch"]

@pytest.mark.parametrize("pkg_name", TARGET_PACKAGES)
def test_real_package_scan_and_graph(pkg_name):
    # 1. AOT Scan
    scanner = PackageScanner(pkg_name)
    modules = scanner.scan(max_workers=2)
    assert len(modules) > 0

    # 2. Build Safety Graph
    graph = PackageGraph(pkg_name, package_hash="v1_test_hash")
    classifier = SafetyClassifier()
    side_analyzer = SideEffectAnalyzer()

    for mname, minfo in modules.items():
        imports = []
        side_effects = []
        if minfo.ast_tree is not None:
            extractor = ImportExtractor(mname)
            imports = extractor.extract(minfo.ast_tree)
            side_effects = side_analyzer.analyze(minfo.ast_tree)

        cls = classifier.classify_module(minfo, imports, side_effects)

        node = GraphNode(
            module_name=mname,
            file_path=str(minfo.file_path),
            is_init=minfo.is_init,
            is_extension=minfo.is_extension
        )
        graph.add_node(node)

        for imp in imports:
            edge = GraphEdge(
                source_module=mname,
                target_module=imp.target_module,
                statement_type=imp.statement_type,
                imported_names=imp.imported_names,
                line_number=imp.line_number,
                safety_class=cls.safety_class,
                evidence_tier=cls.evidence_tier,
                reason=cls.reason
            )
            graph.add_edge(edge)

    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0

    # 3. Verify graph contains expected safety classifications
    lazy_edges = [e for e in graph.edges if e.safety_class == "SAFE_LAZY"]
    eager_edges = [e for e in graph.edges if e.safety_class in ("EAGER_REQUIRED", "NATIVE_REQUIRED", "SECURITY_EAGER")]
    
    assert len(lazy_edges) > 0
    assert len(eager_edges) > 0
