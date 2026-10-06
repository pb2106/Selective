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
from selective.analyzer.security import SecurityAnalyzer, SupplyChainDiff, SEVERITY_WEIGHTS
from selective.analyzer.budget_optimizer import BudgetOptimizer, OptimizationBudget
from selective.deploy.cache_resolver import CacheResolver
from selective.deploy.hook import HookInstaller
from selective.deploy.doctor import SelectiveDoctor
from selective.deploy.preload import Preloader
from selective.deploy.builder import SelectiveArtifactBuilder
from selective.harness.verify import DifferentialVerifier
from selective.harness.bisect import AdvancedBisector, explain_causal_why
from selective.loader.finder import SelectiveFinder
from selective.loader.speculative import SpeculativeScheduler

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

def cmd_security(package_name: str, fail_on: Optional[str] = None, json_out: bool = False) -> int:
    try:
        analyzer = SecurityAnalyzer(package_name)
        report, genome = analyzer.analyze()

        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print("Selective Security Report")
            print("=========================\n")
            print(f"Package: {package_name}")
            print(f"Genome ID: {genome.genome_id}\n")
            for cat, risk in report["categories"].items():
                print(f"{cat:<24} {risk}")
            print(f"\nFindings: {report['findings_count']}")
            print(f"High/Critical: {report['high_critical_count']}")

        if fail_on and fail_on.upper() in SEVERITY_WEIGHTS:
            target_weight = SEVERITY_WEIGHTS[fail_on.upper()]
            report_weight = SEVERITY_WEIGHTS[report["overall_severity"]]
            if report_weight >= target_weight:
                if not json_out:
                    print(f"\n[Selective Security Policy] FAILED: Overall severity {report['overall_severity']} >= threshold {fail_on.upper()}", file=sys.stderr)
                return 1

        return 0
    except Exception as e:
        print(f"Error analyzing security for '{package_name}': {e}", file=sys.stderr)
        return 1

def cmd_security_diff(file_old: str, file_new: str, json_out: bool = False) -> int:
    try:
        old_data = json.loads(Path(file_old).read_text(encoding="utf-8"))
        new_data = json.loads(Path(file_new).read_text(encoding="utf-8"))

        diff = SupplyChainDiff.diff_reports(old_data, new_data)

        if json_out:
            print(json.dumps(diff, indent=2))
        else:
            print("Supply-chain change detected")
            print("============================")
            print(f"\n+ {diff['added_findings_count']} added security findings")
            print(f"- {diff['removed_findings_count']} removed security findings")
            if diff["risk_increased"]:
                print(f"\nRisk increased: {diff['old_overall_severity']} -> {diff['new_overall_severity']}")
            else:
                print(f"\nRisk level: {diff['old_overall_severity']} -> {diff['new_overall_severity']}")

        return 0
    except Exception as e:
        print(f"Error diffing security reports: {e}", file=sys.stderr)
        return 1

def cmd_explain(name: str, why: bool = False, unsafe_only: bool = False, source_diff: bool = False, json_out: bool = False) -> int:
    if why:
        causal = explain_causal_why(name)
        if json_out:
            print(json.dumps(causal, indent=2))
        else:
            print(f"=== Selective Causal Chain for '{name}' ===")
            for step in causal["causal_chain"]:
                print(step)
            print(f"\nReasoning: {causal['explanation']}")
        return 0

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

def cmd_bisect(script_path: str, json_out: bool = False) -> int:
    try:
        bisector = AdvancedBisector(script_path)
        res = bisector.bisect()

        if json_out:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print("Selective Regression Bisect")
            print("===========================")
            print(f"\nVerification result: {'PASSED' if not res.failing_edges else 'FAILED'}")
            print(f"Tests executed: {res.iterations}")

            if res.failing_edges:
                print(f"\nMinimal suspect edge:")
                for edge in res.failing_edges:
                    src = edge.get('source_module', 'app')
                    tgt = edge.get('target_module', 'sub')
                    print(f"    {src} -> {tgt} [{edge.get('safety_class', 'SAFE_LAZY')}]")
                if res.causal_chain:
                    print("\nCausal chain:")
                    for step in res.causal_chain:
                        print(f"    {step}")
                if res.repro_dir:
                    print(f"\nReproduction artifact created at: {res.repro_dir}")
            else:
                print("\nNo regression or failing lazy edge detected.")

        return 0 if not res.failing_edges else 1
    except Exception as e:
        print(f"Error during bisection: {e}", file=sys.stderr)
        return 1

def cmd_build(target_path: str, build_type: str = "generic", bake_dir: Optional[str] = None, json_out: bool = False) -> int:
    try:
        builder = SelectiveArtifactBuilder(target_path, build_type=build_type, bake_dir=bake_dir)
        manifest = builder.build()

        if json_out:
            print(json.dumps(manifest, indent=2))
        else:
            print("Selective Build Summary")
            print("=======================")
            print(f"Build Type: {manifest['build_type']}")
            print(f"Managed Packages: {len(manifest['managed_packages'])}")
            print(f"Modules Deferred: {manifest['total_deferred_modules']}")
            print(f"Cache Size: {manifest['cache_size_bytes'] / 1024.0:.1f} KB")
            print(f"Native Dependencies: {len(manifest['native_dependencies'])}")
            print("\nPerformance Estimates (labeled: estimated):")
            print(f"  Baseline Startup: {manifest['performance_metrics']['baseline_est_ms']} ms")
            print(f"  Optimized Startup: {manifest['performance_metrics']['optimized_est_ms']} ms")
            print(f"  Estimated Speedup: {manifest['performance_metrics']['estimated_speedup_pct']} %")
            print(f"\nArtifact Manifest written to: {manifest['reproducibility']['bake_dir']}/build_manifest.json")

        return 0
    except Exception as e:
        print(f"Error building artifact: {e}", file=sys.stderr)
        return 1

def cmd_optimize(target: str, startup_target: str = "500ms", memory_target: str = "300MB", safety: str = "strict", json_out: bool = False) -> int:
    try:
        budget = OptimizationBudget(startup_target, memory_target, safety)
        optimizer = BudgetOptimizer(target, budget)
        res = optimizer.optimize()

        if json_out:
            print(json.dumps(res, indent=2))
        else:
            print("Optimization Target")
            print("-------------------")
            print(f"Startup: <= {budget.raw_startup_target}")
            print(f"Memory:  <= {budget.raw_memory_target}")
            print(f"Safety:  {budget.safety.upper()}")
            print(f"\nTarget Satisfied: {res['target_satisfied']}")
            print(f"\nSelected Transformations (metric_type: {res['metric_type']}):")
            for t in res["transformations"]:
                print(f"  {t['module']:<25} {t['strategy']:<12} Estimated saving: {t['estimated_saving_ms']} ms (Reason: {t['reason']})")

            if not res["target_satisfied"] and res["blocking_modules"]:
                print("\nBlocking modules (cannot optimize further without violating safety):")
                for bm in res["blocking_modules"]:
                    print(f"  {bm['module']:<25} Reason: {bm['reason']}")

        return 0 if res["target_satisfied"] else 1
    except Exception as e:
        print(f"Error during optimization: {e}", file=sys.stderr)
        return 1

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

def cmd_run(args: List[str], speculative: bool = False) -> int:
    if not args:
        print("Usage: selective run SCRIPT.py [--speculative] [args...]", file=sys.stderr)
        return 1

    script_path = args[0]
    sys.argv = args

    if speculative:
        scheduler = SpeculativeScheduler.get_instance()
        scheduler.start()
        print("[Selective] Background speculative loading enabled")

    cache_dir, _ = CacheResolver.resolve_cache_dir()

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
        for g_file in cache_dir.glob("*_graph.json"):
            try:
                pkg_name = g_file.name.replace("_graph.json", "")
                g = GraphSerializer.load_json(g_file)
                SelectiveFinder.register_package(pkg_name, g)
            except Exception:
                pass

    SelectiveFinder.install()

    with open(script_path, "r") as f:
        code_text = f.read()

    exec(compile(code_text, script_path, "exec"), {"__name__": "__main__"})
    return 0
