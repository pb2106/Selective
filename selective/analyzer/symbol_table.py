"""
Symbol Table Resolver for Selective.
Extracts public definitions, __all__ exports, and re-exports per module.
"""

import ast
from typing import Dict, List, Set, Optional, Tuple, Any

class SymbolBinding:
    def __init__(
        self,
        symbol_name: str,
        defining_module: str,
        source_symbol: str,
        is_reexport: bool = False,
        is_submodule: bool = False,
    ):
        self.symbol_name = symbol_name
        self.defining_module = defining_module
        self.source_symbol = source_symbol
        self.is_reexport = is_reexport
        self.is_submodule = is_submodule

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "defining_module": self.defining_module,
            "source_symbol": self.source_symbol,
            "is_reexport": self.is_reexport,
            "is_submodule": self.is_submodule,
        }

class SymbolTableResolver:
    def __init__(self, module_name: str):
        self.module_name = module_name

    def resolve(self, ast_tree: Optional[ast.AST]) -> Tuple[List[str], Dict[str, SymbolBinding], Optional[List[str]]]:
        """
        Returns:
        (defined_symbols, symbol_bindings_map, __all__ list if defined)
        """
        if ast_tree is None:
            return [], {}, None

        defined_symbols: Set[str] = set()
        bindings: Dict[str, SymbolBinding] = {}
        explicit_all: Optional[List[str]] = None

        # Walk top-level statements
        for node in ast.iter_child_nodes(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_symbols.add(node.name)
                bindings[node.name] = SymbolBinding(
                    symbol_name=node.name,
                    defining_module=self.module_name,
                    source_symbol=node.name,
                    is_reexport=False
                )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name == "__all__":
                            explicit_all = self._extract_all_list(node.value)
                        else:
                            defined_symbols.add(name)
                            bindings[name] = SymbolBinding(
                                symbol_name=name,
                                defining_module=self.module_name,
                                source_symbol=name,
                                is_reexport=False
                            )
            elif isinstance(node, ast.ImportFrom):
                target_mod = node.module or ""
                for alias in node.names:
                    bound_name = alias.asname or alias.name
                    if bound_name != "*":
                        bindings[bound_name] = SymbolBinding(
                            symbol_name=bound_name,
                            defining_module=target_mod,
                            source_symbol=alias.name,
                            is_reexport=True
                        )

        # Filter public names if __all__ is defined
        if explicit_all is not None:
            public_names = explicit_all
        else:
            public_names = [s for s in defined_symbols if not s.startswith("_")]

        return public_names, bindings, explicit_all

    def _extract_all_list(self, expr: ast.AST) -> List[str]:
        elements = []
        if isinstance(expr, (ast.List, ast.Tuple)):
            for elt in expr.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    elements.append(elt.value)
        return elements
