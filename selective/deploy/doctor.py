"""
Diagnostic Doctor for Selective.
Diagnoses environment, cache status, hook installation, and managed package health.
"""

import sys
import os
import site
from pathlib import Path
from typing import Dict, Any
from selective.deploy.cache_resolver import CacheResolver
from selective.deploy.hook import HookInstaller

class SelectiveDoctor:
    @staticmethod
    def diagnose() -> Dict[str, Any]:
        cache_dir, is_writable = CacheResolver.resolve_cache_dir()
        sp_dir = HookInstaller.get_site_packages_dir()
        hook_installed = (sp_dir / "selective.pth").exists()

        # Check installed target packages
        target_pkgs = ["pandas", "scipy", "numpy", "torch"]
        pkg_status = {}
        for p in target_pkgs:
            try:
                mod = __import__(p)
                pkg_status[p] = f"installed ({getattr(mod, '__version__', 'unknown')})"
            except ImportError:
                pkg_status[p] = "not installed"

        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "executable": sys.executable,
            "in_venv": sys.prefix != sys.base_prefix,
            "cache_dir": str(cache_dir),
            "cache_writable": is_writable,
            "site_packages": str(sp_dir),
            "hook_installed": hook_installed,
            "target_packages": pkg_status,
            "selective_disable": os.environ.get("SELECTIVE_DISABLE", "0") == "1",
            "selective_mode": os.environ.get("SELECTIVE_MODE", "conservative"),
        }
