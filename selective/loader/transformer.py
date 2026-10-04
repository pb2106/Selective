"""
AST Source Transformer for Selective.
Implements Strategy B (AST rewriting to lazy proxies and module __getattr__ descriptors)
and Strategy A (Python 3.15+ native __lazy_modules__ injection).
"""

import ast
import sys
from typing import List, Dict, Set, Tuple, Optional, Any
from selective.analyzer.graph_builder import PackageGraph, GraphEdge

class StrategyBTransformer(ast.NodeTransformer):
    def __init__(self, current_module: str, safe_lazy_targets: Set[str], parent_package: str):
        super().__init__()
        self.current_module = current_module
        self.safe_lazy_targets = safe_lazy_targets
        self.parent_package = parent_package
        self.lazy_symbols: Dict[str, Tuple[str, str]] = {} # symbol -> (source_mod, source_symbol)

    def visit_Import(self, node: ast.Import) -> Any:
        # Check if statements are in module scope
        new_nodes = []
        for alias in node.names:
            mod_name = alias.name
            if mod_name in self.safe_lazy_targets:
                bound_name = alias.asname or mod_name.split(".")[0]
                # Replace with bound_name = __selective_lazy_module__("mod_name", "parent_package")
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
        mod_name = node.module or ""
        if mod_name in self.safe_lazy_targets:
            new_nodes = []
            for alias in node.names:
                if alias.name == "*":
                    # Star imports never lazy
                    return node
                bound_name = alias.asname or alias.name
                target_submod = f"{mod_name}.{alias.name}" if mod_name else alias.name
                
                # Create lazy module stub for submodule import
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

            return new_nodes if len(new_nodes) > 1 else new_nodes[0]

        return node

class SelectiveTransformer:
    def __init__(self, current_module: str, package_graph: Optional[PackageGraph] = None):
        self.current_module = current_module
        self.package_graph = package_graph

    def transform(self, tree: ast.AST, strategy: str = "B") -> ast.AST:
        parent_package = self.current_module.split(".")[0]
        safe_lazy_targets: Set[str] = set()

        if self.package_graph is not None:
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
            transformer = StrategyBTransformer(self.current_module, safe_lazy_targets, parent_package)
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
