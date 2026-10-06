"""
AST Import Extractor for Selective.
Extracts module-scope, function-scope, relative, absolute, and star imports from AST trees.
"""

import ast
from typing import List, Dict, Optional, Tuple, Any

class ImportRecord:
    def __init__(
        self,
        statement_type: str,  # 'import', 'from_import', 'star_import'
        target_module: str,
        imported_names: List[Tuple[str, Optional[str]]], # [(name, alias)]
        line_number: int,
        scope: str,  # 'module', 'function', 'class'
        is_type_checking: bool = False,
        is_guarded_branch: bool = False,
        raw_node: Optional[ast.AST] = None,
    ):
        self.statement_type = statement_type
        self.target_module = target_module
        self.imported_names = imported_names
        self.line_number = line_number
        self.scope = scope
        self.is_type_checking = is_type_checking
        self.is_guarded_branch = is_guarded_branch
        self.raw_node = raw_node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "target_module": self.target_module,
            "imported_names": self.imported_names,
            "line_number": self.line_number,
            "scope": self.scope,
            "is_type_checking": self.is_type_checking,
            "is_guarded_branch": self.is_guarded_branch,
        }

def resolve_relative_import(current_module: str, level: int, relative_target: Optional[str], is_init: bool = False) -> str:
    """
    Resolves a relative import (level > 0) or absolute import (level == 0).
    """
    if level == 0:
        return relative_target or ""

    parts = current_module.split(".")
    effective_level = level - 1 if is_init else level

    if effective_level <= 0:
        base_parts = parts
    elif effective_level >= len(parts):
        base_parts = []
    else:
        base_parts = parts[:-effective_level]

    if relative_target:
        if base_parts:
            return ".".join(base_parts) + "." + relative_target
        return relative_target
    return ".".join(base_parts)

class ImportVisitor(ast.NodeVisitor):
    def __init__(self, current_module: str, is_init: bool = False):
        self.current_module = current_module
        self.is_init = is_init
        self.imports: List[ImportRecord] = []
        self._scope_stack: List[str] = ["module"]
        self._type_checking_depth: int = 0
        self._guarded_branch_depth: int = 0

    @property
    def current_scope(self) -> str:
        return self._scope_stack[-1]

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        self._scope_stack.append("class")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_If(self, node: ast.If):
        # Check if test condition is TYPE_CHECKING or sys.version_info / sys.platform
        is_tc = self._is_type_checking_node(node.test)
        is_guarded = self._is_guarded_constant_node(node.test)

        if is_tc:
            self._type_checking_depth += 1
        if is_guarded:
            self._guarded_branch_depth += 1

        self.generic_visit(node)

        if is_tc:
            self._type_checking_depth -= 1
        if is_guarded:
            self._guarded_branch_depth -= 1

    def _is_type_checking_node(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING":
            return True
        return False

    def _is_guarded_constant_node(self, node: ast.AST) -> bool:
        # sys.version_info, sys.platform, os.name, sys.implementation
        names = {"version_info", "platform", "name", "implementation"}
        if isinstance(node, ast.Compare):
            if isinstance(node.left, ast.Attribute) and node.left.attr in names:
                return True
        return False

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            target = alias.name
            names = [(target, alias.asname)]
            rec = ImportRecord(
                statement_type="import",
                target_module=target,
                imported_names=names,
                line_number=node.lineno,
                scope=self.current_scope,
                is_type_checking=self._type_checking_depth > 0,
                is_guarded_branch=self._guarded_branch_depth > 0,
                raw_node=node,
            )
            self.imports.append(rec)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod_target = resolve_relative_import(self.current_module, node.level, node.module, is_init=self.is_init)
        names = []
        is_star = False
        for alias in node.names:
            if alias.name == "*":
                is_star = True
                names.append(("*", None))
            else:
                names.append((alias.name, alias.asname))

        rec = ImportRecord(
            statement_type="star_import" if is_star else "from_import",
            target_module=mod_target,
            imported_names=names,
            line_number=node.lineno,
            scope=self.current_scope,
            is_type_checking=self._type_checking_depth > 0,
            is_guarded_branch=self._guarded_branch_depth > 0,
            raw_node=node,
        )
        self.imports.append(rec)

class ImportExtractor:
    def __init__(self, current_module: str, is_init: bool = False):
        self.current_module = current_module
        self.is_init = is_init

    def extract(self, ast_tree: ast.AST) -> List[ImportRecord]:
        visitor = ImportVisitor(self.current_module, is_init=self.is_init)
        visitor.visit(ast_tree)
        return visitor.imports
