"""
AST Side-Effect Analyzer for Selective.
Statically analyzes module-level AST for side effects (registration calls, atexit/signal,
sys.modules writes, monkey-patching, logging/warnings setup, entry-point enumeration).
"""

import ast
from typing import Dict, List, Set, Tuple, Any, Optional

class SideEffectRecord:
    def __init__(self, category: str, description: str, line_number: int, node: ast.AST):
        self.category = category
        self.description = description
        self.line_number = line_number
        self.node = node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "line_number": self.line_number,
        }

class SideEffectVisitor(ast.NodeVisitor):
    def __init__(self):
        self.side_effects: List[SideEffectRecord] = []
        self._in_def_or_class: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Definitions themselves are not side effects unless decorated with registration decorators
        self._check_decorators(node.decorator_list, node.lineno)
        prev = self._in_def_or_class
        self._in_def_or_class = True
        self.generic_visit(node)
        self._in_def_or_class = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_decorators(node.decorator_list, node.lineno)
        prev = self._in_def_or_class
        self._in_def_or_class = True
        self.generic_visit(node)
        self._in_def_or_class = prev

    def visit_ClassDef(self, node: ast.ClassDef):
        self._check_decorators(node.decorator_list, node.lineno)
        prev = self._in_def_or_class
        self._in_def_or_class = True
        self.generic_visit(node)
        self._in_def_or_class = prev

    def _check_decorators(self, decorators: List[ast.expr], lineno: int):
        if self._in_def_or_class:
            return
        for dec in decorators:
            dec_str = self._ast_to_str(dec)
            if any(k in dec_str for k in ("register", "dispatch", "hook", "option", "command")):
                self.side_effects.append(SideEffectRecord(
                    category="REGISTRATION_DECORATOR",
                    description=f"Module-scope decorator call: @{dec_str}",
                    line_number=lineno,
                    node=dec
                ))

    def visit_Call(self, node: ast.Call):
        if not self._in_def_or_class:
            call_str = self._ast_to_str(node.func)

            # Check atexit / signal / threading / process hooks
            if any(k in call_str for k in ("atexit.register", "signal.signal", "threading.Thread", "os.register_at_fork")):
                self.side_effects.append(SideEffectRecord(
                    category="SYSTEM_HOOK",
                    description=f"System hook registration: {call_str}()",
                    line_number=node.lineno,
                    node=node
                ))
            # Check warnings / logging / audit hooks
            elif any(k in call_str for k in ("logging.basicConfig", "warnings.filterwarnings", "sys.addaudithook")):
                category = "SECURITY_CONFIG" if "audithook" in call_str else "LOGGING_WARNING_CONFIG"
                self.side_effects.append(SideEffectRecord(
                    category=category,
                    description=f"Global state configuration: {call_str}()",
                    line_number=node.lineno,
                    node=node
                ))
            # Check general registration functions
            elif any(k in call_str for k in ("register", "add_command", "dispatch", "set_option")):
                self.side_effects.append(SideEffectRecord(
                    category="REGISTRATION_CALL",
                    description=f"Module-scope registration call: {call_str}()",
                    line_number=node.lineno,
                    node=node
                ))
            # Check entry points / plugin enumeration
            elif any(k in call_str for k in ("entry_points", "iter_modules", "walk_packages")):
                self.side_effects.append(SideEffectRecord(
                    category="PLUGIN_ENUMERATION",
                    description=f"Plugin/entry-point enumeration: {call_str}()",
                    line_number=node.lineno,
                    node=node
                ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if not self._in_def_or_class:
            for target in node.targets:
                target_str = self._ast_to_str(target)
                if "os.environ" in target_str:
                    self.side_effects.append(SideEffectRecord(
                        category="ENV_WRITE",
                        description=f"Environment variable write: {target_str}",
                        line_number=node.lineno,
                        node=node
                    ))
                elif "sys.modules" in target_str:
                    self.side_effects.append(SideEffectRecord(
                        category="SYS_MODULES_MUTATION",
                        description=f"sys.modules manipulation: {target_str}",
                        line_number=node.lineno,
                        node=node
                    ))

        self.generic_visit(node)

    def _ast_to_str(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._ast_to_str(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._ast_to_str(node.func)
        return ""

class SideEffectAnalyzer:
    def analyze(self, ast_tree: Optional[ast.AST]) -> List[SideEffectRecord]:
        if ast_tree is None:
            return []
        visitor = SideEffectVisitor()
        visitor.visit(ast_tree)
        return visitor.side_effects
