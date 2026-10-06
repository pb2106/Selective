"""
Supply-Chain Security & Behavioral Analyzer for Selective.
Performs AOT static security analysis without executing untrusted package code.
Generates Behavioral Genome, Security Report, and Supply-Chain Diffs.
"""

import ast
import sys
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from selective.analyzer.scanner import PackageScanner, ModuleFileInfo
from selective.analyzer.import_extractor import ImportExtractor
from selective.analyzer.native_scanner import NativeScanner

SEVERITY_LEVELS = ["NONE_DETECTED", "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
SEVERITY_WEIGHTS = {lvl: idx for idx, lvl in enumerate(SEVERITY_LEVELS)}

class SecurityFinding:
    def __init__(
        self,
        module_name: str,
        category: str,
        pattern: str,
        evidence: str,
        line_number: int,
        severity: str,
        confidence: float,
        reasoning: str,
    ):
        self.module_name = module_name
        self.category = category
        self.pattern = pattern
        self.evidence = evidence
        self.line_number = line_number
        self.severity = severity
        self.confidence = confidence
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module_name,
            "category": self.category,
            "pattern": self.pattern,
            "evidence": self.evidence,
            "line_number": self.line_number,
            "severity": self.severity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }

class SecurityASTVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.findings: List[SecurityFinding] = []

    def visit_Call(self, node: ast.Call):
        call_str = self._ast_to_str(node.func)

        # Dynamic execution
        if call_str in ("eval", "exec", "compile"):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Dynamic execution",
                pattern=f"{call_str}()",
                evidence=f"Call to {call_str}",
                line_number=node.lineno,
                severity="HIGH",
                confidence=0.95,
                reasoning=f"Arbitrary code execution primitive '{call_str}' detected"
            ))
        elif any(k in call_str for k in ("importlib.import_module", "__import__")):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Dynamic execution",
                pattern=f"{call_str}()",
                evidence=f"Dynamic import via {call_str}",
                line_number=node.lineno,
                severity="MEDIUM",
                confidence=0.90,
                reasoning="Dynamic module import bypassing static dependencies"
            ))

        # System interaction & Process execution
        if any(k in call_str for k in ("subprocess", "os.system", "os.popen", "shutil.rmtree")):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Process execution",
                pattern=f"{call_str}()",
                evidence=f"Process launch via {call_str}",
                line_number=node.lineno,
                severity="HIGH",
                confidence=0.95,
                reasoning="External system process spawning or aggressive filesystem deletion"
            ))
        elif any(k in call_str for k in ("ctypes.", "cffi.", "dlopen")):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Native extensions",
                pattern=f"{call_str}()",
                evidence=f"FFI / C-level library binding: {call_str}",
                line_number=node.lineno,
                severity="MEDIUM",
                confidence=0.90,
                reasoning="Unmanaged C-level foreign function invocation"
            ))
        elif any(k in call_str for k in ("os.remove", "os.unlink", "open")):
            # File system mutation check
            if any(isinstance(arg, ast.Constant) and ("w" in str(arg.value) or "a" in str(arg.value)) for arg in node.args):
                self.findings.append(SecurityFinding(
                    module_name=self.module_name,
                    category="System interaction",
                    pattern=f"{call_str}()",
                    evidence=f"File mutation via {call_str}",
                    line_number=node.lineno,
                    severity="LOW",
                    confidence=0.75,
                    reasoning="File write or modification primitive"
                ))

        # Network behavior
        if any(k in call_str for k in ("socket.socket", "urllib.", "http.client", "requests.", "httpx.", "aiohttp.", "socket.gethostbyname")):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Network capability",
                pattern=f"{call_str}()",
                evidence=f"Network primitive: {call_str}",
                line_number=node.lineno,
                severity="MEDIUM",
                confidence=0.90,
                reasoning="Outbound network or DNS communication capability"
            ))

        # Process/System Hooks & Import Hooks
        if any(k in call_str for k in ("sys.addaudithook", "sys.meta_path.append", "sys.path_hooks.append")):
            self.findings.append(SecurityFinding(
                module_name=self.module_name,
                category="Import hooks",
                pattern=f"{call_str}()",
                evidence=f"Global runtime hook: {call_str}",
                line_number=node.lineno,
                severity="HIGH",
                confidence=0.95,
                reasoning="Interception of system audit events or import resolution hierarchy"
            ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            target_str = self._ast_to_str(target)
            if "os.environ" in target_str:
                self.findings.append(SecurityFinding(
                    module_name=self.module_name,
                    category="Environment mutation",
                    pattern=target_str,
                    evidence="Write to os.environ",
                    line_number=node.lineno,
                    severity="MEDIUM",
                    confidence=0.90,
                    reasoning="Process-wide environment variable modification"
                ))
            elif "sys.meta_path" in target_str or "sys.path_hooks" in target_str:
                self.findings.append(SecurityFinding(
                    module_name=self.module_name,
                    category="Import hooks",
                    pattern=target_str,
                    evidence="Mutation of sys.meta_path / sys.path_hooks",
                    line_number=node.lineno,
                    severity="HIGH",
                    confidence=0.95,
                    reasoning="Modification of global import resolution mechanism"
                ))
        self.generic_visit(node)

    def _ast_to_str(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._ast_to_str(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._ast_to_str(node.value)}[{self._ast_to_str(node.slice)}]"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Call):
            return self._ast_to_str(node.func)
        return ""

class BehavioralGenome:
    def __init__(
        self,
        package_name: str,
        package_version: str,
        modules: List[str],
        import_edges: int,
        native_dependencies: List[str],
        dynamic_imports: int,
        system_interactions: int,
        network_capabilities: int,
        environment_mutations: int,
        security_findings: List[Dict[str, Any]],
    ):
        self.package_name = package_name
        self.package_version = package_version
        self.modules = sorted(modules)
        self.import_edges = import_edges
        self.native_dependencies = sorted(native_dependencies)
        self.dynamic_imports = dynamic_imports
        self.system_interactions = system_interactions
        self.network_capabilities = network_capabilities
        self.environment_mutations = environment_mutations
        self.security_findings = security_findings
        self.genome_id = self._compute_genome_id()

    def _compute_genome_id(self) -> str:
        h = hashlib.sha256()
        payload = json.dumps({
            "name": self.package_name,
            "version": self.package_version,
            "modules": self.modules,
            "edges": self.import_edges,
            "native": self.native_dependencies,
            "dynamic": self.dynamic_imports,
            "system": self.system_interactions,
            "network": self.network_capabilities,
            "env": self.environment_mutations,
            "findings": self.security_findings,
        }, sort_keys=True)
        h.update(payload.encode("utf-8"))
        return f"sha256:{h.hexdigest()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "package_version": self.package_version,
            "genome_id": self.genome_id,
            "modules_count": len(self.modules),
            "import_edges": self.import_edges,
            "native_dependencies": self.native_dependencies,
            "dynamic_imports": self.dynamic_imports,
            "system_interactions": self.system_interactions,
            "network_capabilities": self.network_capabilities,
            "environment_mutations": self.environment_mutations,
            "security_findings": self.security_findings,
        }

class SecurityAnalyzer:
    def __init__(self, package_name: str):
        self.package_name = package_name

    def analyze(self) -> Tuple[Dict[str, Any], BehavioralGenome]:
        scanner = PackageScanner(self.package_name)
        modules = scanner.scan(max_workers=4)

        findings: List[SecurityFinding] = []
        native_libs: Set[str] = set()
        native_scanner = NativeScanner()

        dynamic_count = 0
        sys_interact_count = 0
        network_count = 0
        env_count = 0
        import_edges_count = 0

        for mname, minfo in modules.items():
            if minfo.is_extension:
                native_info = native_scanner.scan_library(minfo.file_path)
                native_libs.update(native_info.needed_libraries)
                findings.append(SecurityFinding(
                    module_name=mname,
                    category="Native extensions",
                    pattern="Compiled extension (.so/.pyd)",
                    evidence=str(minfo.file_path),
                    line_number=0,
                    severity="MEDIUM",
                    confidence=1.0,
                    reasoning="Native compiled C/C++ binary extension"
                ))

            if minfo.ast_tree is not None:
                extractor = ImportExtractor(mname)
                records = extractor.extract(minfo.ast_tree)
                import_edges_count += len(records)

                visitor = SecurityASTVisitor(mname)
                visitor.visit(minfo.ast_tree)
                findings.extend(visitor.findings)

        category_risks: Dict[str, str] = {
            "Dynamic execution": "NONE_DETECTED",
            "Native extensions": "NONE_DETECTED",
            "Network capability": "UNKNOWN", # Default UNKNOWN if static scanner didn't explicitly find network calls
            "Environment mutation": "NONE_DETECTED",
            "Process execution": "NONE_DETECTED",
            "Import hooks": "NONE_DETECTED",
        }

        for f in findings:
            cat = f.category
            if f.category == "Dynamic execution":
                dynamic_count += 1
            elif f.category in ("System interaction", "Process execution"):
                sys_interact_count += 1
            elif f.category == "Network capability":
                network_count += 1
            elif f.category == "Environment mutation":
                env_count += 1

            current_weight = SEVERITY_WEIGHTS[category_risks.get(cat, "NONE_DETECTED")]
            finding_weight = SEVERITY_WEIGHTS[f.severity]
            if finding_weight > current_weight:
                category_risks[cat] = f.severity

        if network_count > 0:
            category_risks["Network capability"] = "MEDIUM"

        overall_weight = max((SEVERITY_WEIGHTS[sev] for sev in category_risks.values()), default=0)
        overall_severity = SEVERITY_LEVELS[overall_weight]

        genome = BehavioralGenome(
            package_name=self.package_name,
            package_version=getattr(__import__(self.package_name, fromlist=["__version__"]), "__version__", "0.0.0") if self.package_name in sys.modules else "1.0.0",
            modules=list(modules.keys()),
            import_edges=import_edges_count,
            native_dependencies=list(native_libs),
            dynamic_imports=dynamic_count,
            system_interactions=sys_interact_count,
            network_capabilities=network_count,
            environment_mutations=env_count,
            security_findings=[f.to_dict() for f in findings],
        )

        report = {
            "package_name": self.package_name,
            "overall_severity": overall_severity,
            "genome_id": genome.genome_id,
            "categories": category_risks,
            "findings_count": len(findings),
            "high_critical_count": sum(1 for f in findings if f.severity in ("HIGH", "CRITICAL")),
            "findings": [f.to_dict() for f in findings],
        }

        return report, genome

class SupplyChainDiff:
    @staticmethod
    def diff_reports(old_report: Dict[str, Any], new_report: Dict[str, Any]) -> Dict[str, Any]:
        old_findings = {f["module"] + ":" + f["pattern"]: f for f in old_report.get("findings", [])}
        new_findings = {f["module"] + ":" + f["pattern"]: f for f in new_report.get("findings", [])}

        added = [f for key, f in new_findings.items() if key not in old_findings]
        removed = [f for key, f in old_findings.items() if key not in new_findings]

        old_sev = old_report.get("overall_severity", "NONE_DETECTED")
        new_sev = new_report.get("overall_severity", "NONE_DETECTED")
        risk_increased = SEVERITY_WEIGHTS[new_sev] > SEVERITY_WEIGHTS[old_sev]

        return {
            "package_name": new_report.get("package_name"),
            "old_genome_id": old_report.get("genome_id"),
            "new_genome_id": new_report.get("genome_id"),
            "risk_increased": risk_increased,
            "old_overall_severity": old_sev,
            "new_overall_severity": new_sev,
            "added_findings_count": len(added),
            "removed_findings_count": len(removed),
            "added_findings": added,
            "removed_findings": removed,
        }
