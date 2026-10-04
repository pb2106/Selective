"""
Pre-fork Preloading Module for Selective.
Pre-resolves expected-use set in parent process before fork to preserve Copy-on-Write memory sharing across worker processes.
"""

import sys
import importlib
from typing import List, Set

class Preloader:
    @staticmethod
    def preload_modules(module_names: List[str]):
        """
        Forces eager loading of specified expected-use modules in parent process.
        """
        for mname in module_names:
            try:
                mod = importlib.import_module(mname)
                # Touch top-level attributes to ensure resolution
                for attr in dir(mod):
                    try:
                        getattr(mod, attr)
                    except Exception:
                        pass
            except Exception:
                pass
