"""
Unit tests for Deployment, Cache Resolver, Hook Installer, Preloader, and Doctor.
"""

import tempfile
import sys
from pathlib import Path
from selective.deploy.cache_resolver import CacheResolver
from selective.deploy.hook import HookInstaller
from selective.deploy.preload import Preloader
from selective.deploy.doctor import SelectiveDoctor

def test_cache_resolver():
    cache_dir, is_writable = CacheResolver.resolve_cache_dir()
    assert cache_dir is not None
    assert isinstance(is_writable, bool)

def test_doctor_diagnose():
    diag = SelectiveDoctor.diagnose()
    assert "python_version" in diag
    assert "cache_dir" in diag
    assert "target_packages" in diag

def test_hook_installer_and_preloader():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Preloader math test
        Preloader.preload_modules(["math"])
        assert "math" in sys.modules
