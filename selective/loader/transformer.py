"""
AST Source Transformer for Selective.
Implements Strategy B (AST rewriting to lazy proxies and module __getattr__ descriptors)
and Strategy A (Python 3.15+ native __lazy_modules__ injection).
"""

import ast
import sys
from typing import List, Dict, Set, Tuple, Optional, Any
from selective.analyzer.graph_builder import PackageGraph, GraphEdge
from selective.analyzer.import_extractor import resolve_relative_import

class StrategyBTransformer(ast.NodeTransformer):
    def __init__(
        self,
        current_module: str,
        safe_lazy_targets: Set[str],
        parent_package: str,
        known_modules: Optional[Set[str]] = None,
        is_init: bool = False
    ):
        super().__init__()
        self.current_module = current_module
        self.safe_lazy_targets = safe_lazy_targets
        self.parent_package = parent_package
        self.known_modules = known_modules or set()
        self.is_init = is_init
        self.lazy_symbols: Dict[str, Tuple[str, str]] = {}

    def visit_Import(self, node: ast.Import) -> Any:
        new_nodes = []
        for alias in node.names:
            mod_name = alias.name
            if mod_name in self.safe_lazy_targets:
                bound_name = alias.asname or mod_name.split(".")[0]
                call_node = ast.Assign(
                    targets=[ast.Name(id=bound_name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="__selective_lazy_module__", ctx=ast.Load()),
                        args=[
                            ast.Constant(value=mod_name),
                            ast.Constant(value=self.parent_package)
                        ],
                        keywords=[]
                    )
                )
                ast.copy_location(call_node, node)
                new_nodes.append(call_node)
            else:
                new_nodes.append(ast.Import(names=[alias]))

        if not new_nodes:
            return None
        return new_nodes if len(new_nodes) > 1 else new_nodes[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        resolved_mod = resolve_relative_import(
            self.current_module,
            node.level,
            node.module,
            is_init=self.is_init
        )

        new_nodes = []
        modified = False

        for alias in node.names:
            if alias.name == "*":
                return node

            bound_name = alias.asname or alias.name
            target_submod = f"{resolved_mod}.{alias.name}" if resolved_mod else alias.name

            # Create lazy proxy only if target_submod is a safe lazy module in known_modules
            if target_submod in self.safe_lazy_targets and (not self.known_modules or target_submod in self.known_modules):
                call_node = ast.Assign(
                    targets=[ast.Name(id=bound_name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="__selective_lazy_module__", ctx=ast.Load()),
                        args=[
                            ast.Constant(value=target_submod),
                            ast.Constant(value=self.parent_package)
                        ],
                        keywords=[]
                    )
                )
                ast.copy_location(call_node, node)
                new_nodes.append(call_node)
                modified = True
            else:
                # Retain original import for symbols or non-lazy modules
                imp_node = ast.ImportFrom(
                    module=node.module,
                    names=[alias],
                    level=node.level
                )
                ast.copy_location(imp_node, node)
                new_nodes.append(imp_node)

        if not modified:
            return node

        return new_nodes if len(new_nodes) > 1 else new_nodes[0]

class SelectiveTransformer:
    def __init__(self, current_module: str, package_graph: Optional[PackageGraph] = None):
        self.current_module = current_module
        self.package_graph = package_graph

    def transform(self, tree: ast.AST, strategy: str = "B") -> ast.AST:
        parent_package = self.current_module.split(".")[0]
        safe_lazy_targets: Set[str] = set()
        known_modules: Set[str] = set()
        is_init = False

        if self.package_graph is not None:
            known_modules = set(self.package_graph.nodes.keys())
            node_info = self.package_graph.nodes.get(self.current_module)
            if node_info is not None:
                is_init = node_info.is_init

            for edge in self.package_graph.edges:
                if edge.source_module == self.current_module and edge.safety_class == "SAFE_LAZY":
                    safe_lazy_targets.add(edge.target_module)

        if strategy == "A" or sys.version_info >= (3, 15):
            # Strategy A: Native __lazy_modules__ injection
            lazy_list_node = ast.Assign(
                targets=[ast.Name(id="__lazy_modules__", ctx=ast.Store())],
                value=ast.List(
                    elts=[ast.Constant(value=mod) for mod in sorted(safe_lazy_targets)],
                    ctx=ast.Load()
                )
            )
            ast.fix_missing_locations(lazy_list_node)
            tree.body.insert(0, lazy_list_node)
            return tree
        else:
            # Strategy B: Source transform
            transformer = StrategyBTransformer(
                self.current_module,
                safe_lazy_targets,
                parent_package,
                known_modules=known_modules,
                is_init=is_init
            )
            transformed_tree = transformer.visit(tree)

            # Prepend import of __selective_lazy_module__ helper if stubs were injected
            helper_import_node = ast.ImportFrom(
                module="selective.loader.miss_path",
                names=[ast.alias(name="lazy_import_module", asname="__selective_lazy_module__")],
                level=0
            )
            ast.fix_missing_locations(helper_import_node)
            transformed_tree.body.insert(0, helper_import_node)

            ast.fix_missing_locations(transformed_tree)
            return transformed_tree
