"""
Unit tests for SymbolTableResolver.
"""

import ast
from selective.analyzer.symbol_table import SymbolTableResolver

def test_symbol_table_basic():
    source = """
__all__ = ["foo", "bar"]

def foo(): pass
def bar(): pass
def _private(): pass

from .sub import baz as BAZ
"""
    tree = ast.parse(source)
    resolver = SymbolTableResolver("pkg.mod")
    public_names, bindings, explicit_all = resolver.resolve(tree)

    assert explicit_all == ["foo", "bar"]
    assert public_names == ["foo", "bar"]
    assert "foo" in bindings
    assert bindings["foo"].defining_module == "pkg.mod"
    assert "BAZ" in bindings
    assert bindings["BAZ"].is_reexport is True
