"""
Graph Builder for Selective.
Constructs Static Dependency Graph (A), Safety Graph (B), and Runtime Plan (C).
"""

from typing import Dict, List, Optional, Set, Any
import json

class GraphNode:
    def __init__(
        self,
        module_name: str,
        file_path: str,
        is_init: bool = False,
        is_extension: bool = False,
        symbols_defined: Optional[List[str]] = None,
        reexports: Optional[Dict[str, str]] = None,
    ):
        self.module_name = module_name
        self.file_path = file_path
        self.is_init = is_init
        self.is_extension = is_extension
        self.symbols_defined = symbols_defined or []
        self.reexports = reexports or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "file_path": self.file_path,
            "is_init": self.is_init,
            "is_extension": self.is_extension,
            "symbols_defined": self.symbols_defined,
            "reexports": self.reexports,
        }

class GraphEdge:
    def __init__(
        self,
        source_module: str,
        target_module: str,
        statement_type: str,
        imported_names: List[Any],
        line_number: int,
        safety_class: str = "UNKNOWN",  # SAFE_LAZY, EAGER_REQUIRED, NATIVE_REQUIRED, SECURITY_EAGER, UNKNOWN
        evidence_tier: int = 0,
        reason: str = "",
    ):
        self.source_module = source_module
        self.target_module = target_module
        self.statement_type = statement_type
        self.imported_names = imported_names
        self.line_number = line_number
        self.safety_class = safety_class
        self.evidence_tier = evidence_tier
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "statement_type": self.statement_type,
            "imported_names": self.imported_names,
            "line_number": self.line_number,
            "safety_class": self.safety_class,
            "evidence_tier": self.evidence_tier,
            "reason": self.reason,
        }

class PackageGraph:
    def __init__(self, package_name: str, package_hash: str = ""):
        self.package_name = package_name
        self.package_hash = package_hash
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.eliminated_edges: List[Dict[str, Any]] = []

    def add_node(self, node: GraphNode):
        self.nodes[node.module_name] = node

    def add_edge(self, edge: GraphEdge):
        self.edges.append(edge)

    def add_eliminated_edge(self, source: str, target: str, reason: str, lineno: int):
        self.eliminated_edges.append({
            "source": source,
            "target": target,
            "reason": reason,
            "line_number": lineno
        })

    def get_dependencies(self, module_name: str) -> List[GraphEdge]:
        return [e for e in self.edges if e.source_module == module_name]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "package_hash": self.package_hash,
            "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "eliminated_edges": self.eliminated_edges,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageGraph":
        graph = cls(data["package_name"], data.get("package_hash", ""))
        for name, ndata in data.get("nodes", {}).items():
            node = GraphNode(
                module_name=ndata["module_name"],
                file_path=ndata["file_path"],
                is_init=ndata.get("is_init", False),
                is_extension=ndata.get("is_extension", False),
                symbols_defined=ndata.get("symbols_defined", []),
                reexports=ndata.get("reexports", {}),
            )
            graph.add_node(node)
        for edata in data.get("edges", []):
            edge = GraphEdge(
                source_module=edata["source_module"],
                target_module=edata["target_module"],
                statement_type=edata["statement_type"],
                imported_names=edata["imported_names"],
                line_number=edata["line_number"],
                safety_class=edata.get("safety_class", "UNKNOWN"),
                evidence_tier=edata.get("evidence_tier", 0),
                reason=edata.get("reason", ""),
            )
            graph.add_edge(edge)
        graph.eliminated_edges = data.get("eliminated_edges", [])
        return graph

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "PackageGraph":
        return cls.from_dict(json.loads(json_str))
