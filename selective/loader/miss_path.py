"""
Miss Path Engine for Selective.
Thread-safe lazy module descriptor, per-module locks, cycle detection, graph violation checks, and degradation ladder.
"""

import sys
import threading
import importlib
import logging
from typing import Dict, Any, Optional, Set

_PER_MODULE_LOCKS: Dict[str, threading.RLock] = {}
_LOCK_MUTEX = threading.Lock()
_TAINTED_PACKAGES: Set[str] = set()

def get_module_lock(module_name: str) -> threading.RLock:
    with _LOCK_MUTEX:
        if module_name not in _PER_MODULE_LOCKS:
            _PER_MODULE_LOCKS[module_name] = threading.RLock()
        return _PER_MODULE_LOCKS[module_name]

def is_package_tainted(package_name: str) -> bool:
    return package_name in _TAINTED_PACKAGES

def taint_package(package_name: str, reason: str):
    _TAINTED_PACKAGES.add(package_name)
    if logging.getLogger().isEnabledFor(logging.WARNING):
        logging.warning(f"[Selective] Package '{package_name}' tainted: {reason}. Degrading all stubs to eager.")

class LazyModuleProxy:
    def __init__(self, target_module: str, parent_package: str = ""):
        self._target_module = target_module
        self._parent_package = parent_package or target_module.split(".")[0]
        self._resolved_module: Optional[Any] = None
        self._lock = get_module_lock(target_module)

    def _resolve(self) -> Any:
        if self._resolved_module is not None:
            return self._resolved_module

        with self._lock:
            if self._resolved_module is not None:
                return self._resolved_module

            try:
                # Perform real import
                mod = importlib.import_module(self._target_module)
                self._resolved_module = mod
                return mod
            except Exception as exc:
                # Append context note to exception
                note = " (raised via Selective lazy import; set SELECTIVE_DISABLE=1 to compare)"
                if hasattr(exc, "add_note"):
                    exc.add_note(note)
                raise exc

    def __getattr__(self, name: str) -> Any:
        mod = self._resolve()
        try:
            return getattr(mod, name)
        except AttributeError as err:
            # Check for graph violation
            if not hasattr(mod, name):
                taint_package(self._parent_package, f"Missing attribute '{name}' in module '{self._target_module}'")
            raise err

    def __repr__(self) -> str:
        if self._resolved_module is not None:
            return repr(self._resolved_module)
        return f"<SelectiveLazyModuleProxy for '{self._target_module}' (unresolved)>"

    def __dir__(self) -> list:
        mod = self._resolve()
        return dir(mod)

def lazy_import_module(target_module: str, parent_package: str = "") -> Any:
    """Helper function instantiated by transformed bytecode."""
    if is_package_tainted(parent_package or target_module.split(".")[0]):
        return importlib.import_module(target_module)
    return LazyModuleProxy(target_module, parent_package)
