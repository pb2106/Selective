"""
Command implementations for Selective CLI.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from selective.analyzer.scanner import PackageScanner
from selective.analyzer.import_extractor import ImportExtractor
from selective.analyzer.side_effects import SideEffectAnalyzer
from selective.analyzer.classifier import SafetyClassifier
from selective.analyzer.graph_builder import PackageGraph, GraphNode, GraphEdge
from selective.analyzer.serializer import GraphSerializer
from selective.deploy.cache_resolver import CacheResolver
from selective.deploy.hook import HookInstaller
from selective.deploy.doctor import SelectiveDoctor
from selective.deploy.preload import Preloader
from selective.harness.verify import DifferentialVerifier
from selective.harness.bisect import EdgeBisector
from selective.loader.finder import SelectiveFinder

def cmd_scan(package_name: str, bake_dir: Optional[str] = None, json_out: bool = False) -> int:
    try:
        scanner = PackageScanner(package_name)
        modules = scanner.scan(max_workers=4)

        graph = PackageGraph(package_name)
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

        cache_dir, _ = CacheResolver.resolve_cache_dir()
        out_dir = Path(bake_dir) if bake_dir else cache_dir
        out_path = out_dir / f"{package_name}_graph.json"
        GraphSerializer.save_json(graph, out_path)

        if json_out:
            print(graph.to_json())
        else:
            print(f"[Selective] Successfully scanned '{package_name}'. Graph written to: {out_path}")
            print(f"  Total modules: {len(graph.nodes)}")
            print(f"  Total edges: {len(graph.edges)}")

        return 0
    except Exception as e:
        print(f"Error scanning package '{package_name}': {e}", file=sys.stderr)
        return 1

def cmd_explain(name: str, unsafe_only: bool = False, source_diff: bool = False, json_out: bool = False) -> int:
    cache_dir, _ = CacheResolver.resolve_cache_dir()
    pkg_name = name.split(".")[0]
    graph_path = cache_dir / f"{pkg_name}_graph.json"

    if not graph_path.exists():
        print(f"[Selective] No graph found for '{pkg_name}'. Run 'selective scan {pkg_name}' first.", file=sys.stderr)
        return 1

    graph = GraphSerializer.load_json(graph_path)
    edges = [e for e in graph.edges if e.source_module == name or e.target_module == name]

    if unsafe_only:
        edges = [e for e in edges if e.safety_class in ("EAGER_REQUIRED", "NATIVE_REQUIRED", "SECURITY_EAGER", "UNKNOWN")]

    explanation = {
        "target": name,
        "total_associated_edges": len(edges),
        "edges": [e.to_dict() for e in edges]
    }

    if json_out:
        print(json.dumps(explanation, indent=2))
    else:
        print(f"=== Selective Explanation for '{name}' ===")
        for e in edges:
            print(f"  {e.source_module} -> {e.target_module} [{e.safety_class} | Tier {e.evidence_tier}] Reason: {e.reason}")

    return 0

def cmd_verify(script_path: str, json_out: bool = False) -> int:
    verifier = DifferentialVerifier(script_path)
    res = verifier.verify()
    if json_out:
        print(json.dumps(res, indent=2))
    else:
        if res["passed"]:
            print(f"[Selective Verify] PASSED: Baseline and Selective runs are observably equivalent.")
        else:
            print(f"[Selective Verify] FAILED: Diffs detected across levels:", file=sys.stderr)
            print(json.dumps(res["diffs"], indent=2), file=sys.stderr)
    return 0 if res["passed"] else 1

def cmd_doctor(json_out: bool = False) -> int:
    diag = SelectiveDoctor.diagnose()
    if json_out:
        print(json.dumps(diag, indent=2))
    else:
        print("=== Selective Doctor Diagnostics ===")
        for k, v in diag.items():
            print(f"  {k}: {v}")
    return 0

def cmd_install_hook() -> int:
    pth_file = HookInstaller.install_hook()
    print(f"[Selective] Hook installed into active venv: {pth_file}")
    return 0

def cmd_uninstall_hook() -> int:
    removed = HookInstaller.uninstall_hook()
    if removed:
        print("[Selective] Hook successfully uninstalled.")
    else:
        print("[Selective] Hook was not installed.")
    return 0

def cmd_run(args: List[str]) -> int:
    if not args:
        print("Usage: selective run SCRIPT.py [args...]", file=sys.stderr)
        return 1

    script_path = args[0]
    sys.argv = args

    # Auto-register top-level package if scanning graph exists
    top_pkg = Path(script_path).stem
    cache_dir, _ = CacheResolver.resolve_cache_dir()

    # Enable SelectiveFinder
    SelectiveFinder.install()

    with open(script_path, "r") as f:
        code_text = f.read()

    exec(compile(code_text, script_path, "exec"), {"__name__": "__main__"})
    return 0
