"""
Unit tests for ImportExtractor.
"""

import ast
import pytest
from selective.analyzer.import_extractor import ImportExtractor, resolve_relative_import

def test_resolve_relative_import():
    assert resolve_relative_import("pkg.sub.mod", 1, "helper") == "pkg.sub.helper"
    assert resolve_relative_import("pkg.sub.mod", 2, "utils") == "pkg.utils"
    assert resolve_relative_import("pkg.sub.mod", 1, None) == "pkg.sub"

def test_import_extractor_basic():
    source = """
import os
import sys as system
from pathlib import Path
from . import submod
from ..utils import helper as h
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import scipy

def f():
    import json
"""
    tree = ast.parse(source)
    extractor = ImportExtractor("pkg.core.main")
    records = extractor.extract(tree)

    modules_imported = [r.target_module for r in records]
    assert "os" in modules_imported
    assert "sys" in modules_imported
    assert "pathlib" in modules_imported
    assert "pkg.core" in modules_imported
    assert "pkg.utils" in modules_imported
    assert "scipy" in modules_imported
    assert "json" in modules_imported

    # Check scopes
    json_rec = [r for r in records if r.target_module == "json"][0]
    assert json_rec.scope == "function"

    # Check TYPE_CHECKING flag
    scipy_rec = [r for r in records if r.target_module == "scipy"][0]
    assert scipy_rec.is_type_checking is True
