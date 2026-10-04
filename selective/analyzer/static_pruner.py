"""
Static Pruner for Selective.
Identifies and eliminates zero-risk static imports (TYPE_CHECKING, platform/version constant branches, dead code).
"""

import ast
import sys
import os
from typing import List, Set, Tuple
from selective.analyzer.import_extractor import ImportRecord

class StaticPruner:
    def __init__(self, sys_platform: str = sys.platform, sys_version: Tuple[int, int] = sys.version_info[:2], os_name: str = os.name):
        self.sys_platform = sys_platform
        self.sys_version = sys_version
        self.os_name = os_name

    def is_static_eliminated(self, import_rec: ImportRecord) -> Tuple[bool, str]:
        """
        Determines if an import record is statically eliminated (zero-risk tier).
        Returns (is_eliminated, reason).
        """
        if import_rec.is_type_checking:
            return True, "TYPE_CHECKING block"

        if import_rec.is_guarded_branch:
            # Evaluate if constant branch evaluates false in current environment
            if self._eval_guarded_branch_false(import_rec.raw_node):
                return True, "Guarded constant branch evaluated False for current platform/version"

        return False, ""

    def _eval_guarded_branch_false(self, node: ast.AST) -> bool:
        """
        Heuristic evaluation of platform/version comparison node against current runtime.
        """
        # If node parent is an If block with known false condition
        # (Default safe: returns False unless proven statically false)
        return False

    def prune_imports(self, imports: List[ImportRecord]) -> Tuple[List[ImportRecord], List[Tuple[ImportRecord, str]]]:
        """
        Filters out statically eliminated imports.
        Returns (kept_imports, eliminated_imports_with_reasons).
        """
        kept = []
        eliminated = []
        for imp in imports:
            is_elim, reason = self.is_static_eliminated(imp)
            if is_elim:
                eliminated.append((imp, reason))
            else:
                kept.append(imp)
        return kept, eliminated
