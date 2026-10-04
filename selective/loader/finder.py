"""
SelectiveFinder MetaPathFinder implementation.
Fast-reject finder with O(1) set lookup for unmanaged package names and fast fingerprint verification.
"""

import sys
import importlib.abc
import importlib.util
from pathlib import Path
from typing import Set, Dict, Optional, Any, Sequence
from selective.loader.loader import SelectiveLoader
from selective.loader.controls import SelectiveConfig
from selective.analyzer.graph_builder import PackageGraph

class SelectiveFinder(importlib.abc.MetaPathFinder):
    _managed_packages: Set[str] = set()
    _package_graphs: Dict[str, PackageGraph] = {}
    _installed: bool = False

    @classmethod
    def register_package(cls, package_name: str, package_graph: Optional[PackageGraph] = None):
        cls._managed_packages.add(package_name)
        if package_graph is not None:
            cls._package_graphs[package_name] = package_graph

    @classmethod
    def install(cls):
        if not cls._installed:
            sys.meta_path.insert(0, cls())
            cls._installed = True

    @classmethod
    def uninstall(cls):
        sys.meta_path = [f for f in sys.meta_path if not isinstance(f, cls)]
        cls._installed = False

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[Any] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        # Fast path 1: Check kill switch
        if SelectiveConfig.is_disabled():
            return None

        # Fast path 2: O(1) check against managed top-level names
        top_name = fullname.split(".")[0]
        if top_name not in self._managed_packages:
            return None

        # Managed package: find standard file spec
        graph = self._package_graphs.get(top_name)

        # Standard loader lookup
        spec = None
        for finder in sys.meta_path:
            if finder is not self and hasattr(finder, "find_spec"):
                spec = finder.find_spec(fullname, path, target)
                if spec is not None and spec.origin and spec.origin.endswith(".py"):
                    break

        if spec is not None and spec.origin and spec.origin.endswith(".py"):
            loader = SelectiveLoader(fullname, spec.origin, graph)
            return importlib.util.spec_from_loader(
                fullname,
                loader,
                origin=spec.origin,
                is_pkg=spec.submodule_search_locations is not None
            )

        return None
