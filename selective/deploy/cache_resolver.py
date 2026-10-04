"""
Cache Location Resolver for Selective.
Resolves multi-tier cache path hierarchy and handles read-only environment fallbacks.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

class CacheResolver:
    @staticmethod
    def resolve_cache_dir() -> Tuple[Path, bool]:
        """
        Returns (cache_directory_path, is_writable).
        Resolution order:
        1. SELECTIVE_CACHE env var
        2. ./.selective/ (project directory)
        3. <venv>/selective-cache/
        4. ~/.cache/selective/
        """
        candidates = []

        # 1. Environment Variable
        env_cache = os.environ.get("SELECTIVE_CACHE")
        if env_cache:
            candidates.append(Path(env_cache))

        # 2. Project Directory
        candidates.append(Path.cwd() / ".selective")

        # 3. Active Virtual Environment
        if sys.prefix != sys.base_prefix:
            candidates.append(Path(sys.prefix) / "selective-cache")

        # 4. User Home Cache
        candidates.append(Path.home() / ".cache" / "selective")

        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                test_file = candidate / ".write_test"
                test_file.touch()
                test_file.unlink()
                return candidate, True
            except (OSError, PermissionError):
                if candidate.exists() and os.access(candidate, os.R_OK):
                    return candidate, False

        fallback = Path.home() / ".cache" / "selective"
        return fallback, False
