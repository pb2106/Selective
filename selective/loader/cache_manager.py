"""
Transformed Bytecode Cache Manager for Selective.
Manages isolated binary bytecode cache keyed by source hash, graph ID, transform version, and Python magic number.
"""

import os
import hashlib
import marshal
import importlib.util
from pathlib import Path
from typing import Optional, Any
from types import CodeType

TRANSFORM_VERSION = 6
MAGIC_NUMBER = importlib.util.MAGIC_NUMBER

_GLOBAL_CACHE_MANAGER: Optional["BytecodeCacheManager"] = None

def get_cache_manager() -> "BytecodeCacheManager":
    global _GLOBAL_CACHE_MANAGER
    if _GLOBAL_CACHE_MANAGER is None:
        _GLOBAL_CACHE_MANAGER = BytecodeCacheManager()
    return _GLOBAL_CACHE_MANAGER

class BytecodeCacheManager:
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "selective" / "bytecode"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_cache_key(self, source_path: str, graph_id: str, source_text: Optional[str] = None) -> str:
        h = hashlib.md5()
        try:
            st = os.stat(source_path)
            key_str = f"{source_path}:{st.st_mtime_ns}:{st.st_size}:{graph_id}:{TRANSFORM_VERSION}"
            h.update(key_str.encode("utf-8"))
        except Exception:
            if source_text is not None:
                h.update(source_text.encode("utf-8"))
            h.update(graph_id.encode("utf-8"))
            h.update(str(TRANSFORM_VERSION).encode("utf-8"))
        h.update(MAGIC_NUMBER)
        return h.hexdigest()

    def get(self, source_path: str, graph_id: str, source_text: Optional[str] = None) -> Optional[CodeType]:
        key = self._compute_cache_key(source_path, graph_id, source_text)
        cache_path = self.cache_dir / f"{key}.pyc"
        if not cache_path.exists():
            return None

        try:
            data = cache_path.read_bytes()
            code_obj = marshal.loads(data)
            if isinstance(code_obj, CodeType):
                return code_obj
        except Exception:
            pass
        return None

    def put(self, source_path: str, graph_id: str, code_obj: CodeType, source_text: Optional[str] = None):
        key = self._compute_cache_key(source_path, graph_id, source_text)
        cache_path = self.cache_dir / f"{key}.pyc"
        try:
            data = marshal.dumps(code_obj)
            cache_path.write_bytes(data)
        except Exception:
            pass
