"""
Unit tests for PackageScanner.
"""

import tempfile
from pathlib import Path
import pytest
from selective.analyzer.scanner import PackageScanner, ModuleFileInfo

def test_scanner_on_synthetic_package():
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "dummy_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("import dummy_pkg.sub; x = 1\n", encoding="utf-8")
        
        sub_dir = pkg_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text("from . import helper\n", encoding="utf-8")
        (sub_dir / "helper.py").write_text("def foo(): return 42\n", encoding="utf-8")

        scanner = PackageScanner(str(pkg_dir))
        modules = scanner.scan(max_workers=1)

        assert "dummy_pkg" in modules
        assert "dummy_pkg.sub" in modules
        assert "dummy_pkg.sub.helper" in modules

        assert modules["dummy_pkg"].is_init is True
        assert modules["dummy_pkg"].ast_tree is not None
        assert modules["dummy_pkg.sub.helper"].is_init is False

def test_scanner_syntax_error_handling():
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "bad_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("this is invalid python syntax !!!\n", encoding="utf-8")

        scanner = PackageScanner(str(pkg_dir))
        modules = scanner.scan(max_workers=1)

        assert "bad_pkg" in modules
        assert modules["bad_pkg"].ast_tree is None
        assert "AST parse error" in modules["bad_pkg"].error
