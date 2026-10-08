"""
Runtime Controls and Configuration Flags for Selective.
"""

import os
from typing import Optional

class SelectiveConfig:
    CONTROL_KEYS = frozenset({
        "SELECTIVE_DISABLE",
        "SELECTIVE_MODE",
        "SELECTIVE_STRICT",
        "SELECTIVE_LOG",
        "SELECTIVE_BAKED_CACHE",
        "SELECTIVE_SPECULATIVE",
        "SELECTIVE_CACHE",
    })

    @staticmethod
    def is_disabled() -> bool:
        return os.environ.get("SELECTIVE_DISABLE", "0") == "1"

    @staticmethod
    def get_mode() -> str:
        return os.environ.get("SELECTIVE_MODE", "conservative").lower()

    @staticmethod
    def is_strict() -> bool:
        return os.environ.get("SELECTIVE_STRICT", "0") == "1"

    @staticmethod
    def get_log_path() -> Optional[str]:
        return os.environ.get("SELECTIVE_LOG", None)
