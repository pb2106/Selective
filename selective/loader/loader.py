"""
SelectiveLoader implementation.
Subclasses importlib.abc.SourceLoader to serve dynamically transformed AST bytecode.
"""

import ast
import sys
import importlib.abc
import importlib.util
from pathlib import Path
from types import CodeType
from typing import Optional, Any
from selective.loader.transformer import SelectiveTransformer
from selective.loader.cache_manager import get_cache_manager
from selective.analyzer.graph_builder import PackageGraph

class SelectiveLoader(importlib.abc.SourceLoader):
    def __init__(self, fullname: str, path: str, package_graph: Optional[PackageGraph] = None):
        self.fullname = fullname
        self.path = path
        self.package_graph = package_graph
        self.cache_manager = get_cache_manager()

    def get_filename(self, fullname: str) -> str:
        return self.path

    def exec_module(self, module: Any) -> None:
        if not hasattr(module, "__file__") or getattr(module, "__file__", None) is None:
            module.__file__ = self.path
        super().exec_module(module)

    def get_data(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def get_code(self, fullname: str) -> Optional[CodeType]:
        graph_id = self.package_graph.package_hash if self.package_graph else "default"

        # 0. Speculative prepared code check
        from selective.loader.speculative import SpeculativeScheduler
        prepared_code = SpeculativeScheduler.get_instance().get_prepared_code(fullname)
        if prepared_code is not None:
            return prepared_code

        # 1. Bytecode cache lookup (fast mtime/size check)
        cached_code = self.cache_manager.get(self.path, graph_id)
        if cached_code is not None:
            return cached_code

        # 2. Read source text and transform AST
        source_bytes = self.get_data(self.path)
        source_text = source_bytes.decode("utf-8", errors="replace")

        try:
            tree = ast.parse(source_text, filename=self.path)
            transformer = SelectiveTransformer(fullname, self.package_graph)
            transformed_tree = transformer.transform(tree)

            compiled_code = compile(transformed_tree, filename=self.path, mode="exec")

            # 3. Store in bytecode cache
            self.cache_manager.put(self.path, graph_id, compiled_code, source_text)
            return compiled_code
        except Exception:
            # Fallback to standard compilation on transform error
            return compile(source_text, filename=self.path, mode="exec")
