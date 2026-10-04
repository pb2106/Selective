"""
Command implementations for Selective CLI.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from selective.analyzer.scanner import PackageScanner, ProjectScanner
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

def _scan_single_package(package_name: str, cache_dir: Path) -> PackageGraph:
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

    out_path = cache_dir / f"{package_name}_graph.json"
    GraphSerializer.save_json(graph, out_path)
    SelectiveFinder.register_package(package_name, graph)
    return graph

def cmd_scan(target: str, is_project: bool = False, bake_dir: Optional[str] = None, json_out: bool = False) -> int:
    try:
        cache_dir, _ = CacheResolver.resolve_cache_dir()
        out_dir = Path(bake_dir) if bake_dir else cache_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        target_path = Path(target).resolve()
        
        # Determine if target is a project directory
        is_project_dir = is_project or (target_path.exists() and target_path.is_dir() and not (target_path / "__init__.py").exists())

        if is_project_dir:
            if not json_out:
                print(f"[Selective] Scanning project directory at '{target_path}'...")
            
            project_scanner = ProjectScanner(str(target_path))
            deps = project_scanner.discover_third_party_dependencies()

            if not json_out:
                print(f"[Selective] Discovered {len(deps)} third-party package dependencies: {', '.join(sorted(deps))}")

            scanned_graphs: Dict[str, Any] = {}
            for pkg in sorted(deps):
                if not json_out:
                    print(f"  Scanning package '{pkg}'...")
                try:
                    graph = _scan_single_package(pkg, out_dir)
                    scanned_graphs[pkg] = {
                        "nodes": len(graph.nodes),
                        "edges": len(graph.edges)
                    }
                except Exception as pkg_err:
                    if not json_out:
                        print(f"  Warning: Failed to scan package '{pkg}': {pkg_err}", file=sys.stderr)

            # Save project manifest
            manifest = {
                "project_path": str(target_path),
                "managed_dependencies": list(sorted(deps)),
                "scanned_graphs": scanned_graphs
            }
            manifest_path = out_dir / "project_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            if json_out:
                print(json.dumps(manifest, indent=2))
            else:
                print(f"[Selective] Project scan complete. Manifest written to: {manifest_path}")

            return 0
        else:
            # Single package scan
            graph = _scan_single_package(target, out_dir)
            out_path = out_dir / f"{target}_graph.json"

            if json_out:
                print(graph.to_json())
            else:
                print(f"[Selective] Successfully scanned package '{target}'. Graph written to: {out_path}")
                print(f"  Total modules: {len(graph.nodes)}")
                print(f"  Total edges: {len(graph.edges)}")

            return 0

    except Exception as e:
        print(f"Error scanning '{target}': {e}", file=sys.stderr)
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

    cache_dir, _ = CacheResolver.resolve_cache_dir()

    # Load project manifest if available
    manifest_path = cache_dir / "project_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for pkg in manifest.get("managed_dependencies", []):
                g_path = cache_dir / f"{pkg}_graph.json"
                if g_path.exists():
                    g = GraphSerializer.load_json(g_path)
                    SelectiveFinder.register_package(pkg, g)
        except Exception:
            pass
    else:
        # Fallback: load all available package graphs in cache
        for g_file in cache_dir.glob("*_graph.json"):
            try:
                pkg_name = g_file.name.replace("_graph.json", "")
                g = GraphSerializer.load_json(g_file)
                SelectiveFinder.register_package(pkg_name, g)
            except Exception:
                pass

    # Enable SelectiveFinder
    SelectiveFinder.install()

    with open(script_path, "r") as f:
        code_text = f.read()

    exec(compile(code_text, script_path, "exec"), {"__name__": "__main__"})
    return 0
