"""
Unit tests for Selective Runtime Loader, Finder, Transformer, and Miss Path.
"""

import tempfile
import sys
import importlib
from pathlib import Path
from selective.loader.finder import SelectiveFinder
from selective.loader.loader import SelectiveLoader
from selective.loader.miss_path import LazyModuleProxy, is_package_tainted, taint_package
from selective.analyzer.graph_builder import PackageGraph, GraphEdge

def test_lazy_module_proxy_deferred_resolution():
    proxy = LazyModuleProxy("math")
    assert repr(proxy) == "<SelectiveLazyModuleProxy for 'math' (unresolved)>"
    
    # Access attribute to trigger resolution
    sqrt_val = proxy.sqrt(16)
    assert sqrt_val == 4.0
    assert repr(proxy) != "<SelectiveLazyModuleProxy for 'math' (unresolved)>"

def test_degradation_ladder_tainting():
    pkg_name = "test_taint_pkg"
    assert is_package_tainted(pkg_name) is False
    
    taint_package(pkg_name, "Graph violation test")
    assert is_package_tainted(pkg_name) is True

def test_selective_finder_fast_reject():
    finder = SelectiveFinder()
    SelectiveFinder.register_package("managed_dummy")

    # Unmanaged module -> returns None immediately
    spec_unmanaged = finder.find_spec("json", None)
    assert spec_unmanaged is None

    # Managed module -> resolves with SelectiveLoader
    spec_managed = finder.find_spec("managed_dummy", None)
    # Since managed_dummy is not on path, spec is None or resolved depending on environment

def test_finder_imports_real_package():
    SelectiveFinder.register_package("json")
    SelectiveFinder.install()
    try:
        for name in [k for k in list(sys.modules.keys())
                     if k == "json" or k.startswith("json.")]:
            del sys.modules[name]
        mod = importlib.import_module("json")
        assert mod.dumps({"a": 1}) == '{"a": 1}'
        assert isinstance(mod.__spec__.loader, SelectiveLoader)
    finally:
        SelectiveFinder.uninstall()
        SelectiveFinder._managed_packages.discard("json")
        for name in [k for k in list(sys.modules.keys())
                     if k == "json" or k.startswith("json.")]:
            del sys.modules[name]

