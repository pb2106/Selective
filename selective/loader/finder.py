"""
SelectiveFinder MetaPathFinder implementation.
Fast-reject finder with O(1) set lookup for unmanaged package names and fast fingerprint verification.
"""

import sys
import importlib.abc
import importlib.util
from pathlib import Path
from typing import Set, Dict, Optional, Any, Sequence, Tuple
from selective.loader.loader import SelectiveLoader
from selective.loader.controls import SelectiveConfig
from selective.analyzer.graph_builder import PackageGraph

NEVER_LAZY_PREFIXES = (
    "torch._logging",
    "torch._C",
    "torch._ops",
    "torch._library",
    "torch.fx.experimental._constant_symnode",
)

class SelectiveFinder(importlib.abc.MetaPathFinder):
    _managed_packages: Set[str] = set()
    _package_graphs: Dict[str, PackageGraph] = {}
    _spec_cache: Dict[str, Optional[Tuple[str, bool, Optional[Sequence[str]]]]] = {}
    _installed: bool = False

    @classmethod
    def register_package(cls, package_name: str, package_graph: Optional[PackageGraph] = None):
        cls._managed_packages.add(package_name)
        if package_graph is not None:
            cls._package_graphs[package_name] = package_graph

    @classmethod
    def get_package_graph(cls, package_name: str) -> Optional[PackageGraph]:
        if package_name not in cls._package_graphs:
            from selective.deploy.cache_resolver import CacheResolver
            from selective.analyzer.serializer import GraphSerializer
            cache_dir, _ = CacheResolver.resolve_cache_dir()
            g_path = cache_dir / f"{package_name}_graph.json"
            if g_path.exists():
                try:
                    cls._package_graphs[package_name] = GraphSerializer.load_json(g_path)
                except Exception:
                    cls._package_graphs[package_name] = None
            else:
                cls._package_graphs[package_name] = None
        return cls._package_graphs.get(package_name)

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

        # Safety check: Never lazy critical internal module prefixes
        if fullname.startswith(NEVER_LAZY_PREFIXES):
            return None

        # Fast path 2: O(1) check against managed top-level names
        top_name = fullname.split(".")[0]
        if top_name not in self._managed_packages:
            return None

        graph = self.get_package_graph(top_name)

        # Fast path 3: Spec origin cache
        if fullname in self._spec_cache:
            cache_item = self._spec_cache[fullname]
            if cache_item is None:
                return None
            origin, is_pkg, search_locs = cache_item
            loader = SelectiveLoader(fullname, origin, graph)
            res_spec = importlib.util.spec_from_loader(
                fullname,
                loader,
                origin=origin,
                is_package=is_pkg
            )
            if res_spec is not None and search_locs is not None:
                res_spec.submodule_search_locations = search_locs
            return res_spec

        # Standard loader lookup
        spec = None
        for finder in sys.meta_path:
            if not isinstance(finder, SelectiveFinder) and hasattr(finder, "find_spec"):
                spec = finder.find_spec(fullname, path, target)
                if spec is not None and spec.origin and spec.origin.endswith(".py"):
                    break

        if spec is not None and spec.origin and spec.origin.endswith(".py"):
            is_pkg = spec.submodule_search_locations is not None
            self._spec_cache[fullname] = (spec.origin, is_pkg, spec.submodule_search_locations)
            loader = SelectiveLoader(fullname, spec.origin, graph)
            res_spec = importlib.util.spec_from_loader(
                fullname,
                loader,
                origin=spec.origin,
                is_package=is_pkg
            )
            if res_spec is not None and spec.submodule_search_locations is not None:
                res_spec.submodule_search_locations = spec.submodule_search_locations
            return res_spec

        self._spec_cache[fullname] = None
        return None
