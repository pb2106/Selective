"""
Package Scanner for Selective.
Discovers and parses Python package files statically using AST without code execution.
"""

import os
import sys
import ast
import hashlib
import importlib.util
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple, Any

class ModuleFileInfo:
    def __init__(
        self,
        module_name: str,
        file_path: Path,
        relative_path: str,
        file_hash: str,
        is_init: bool,
        is_extension: bool,
        ast_tree: Optional[ast.AST] = None,
        error: Optional[str] = None,
    ):
        self.module_name = module_name
        self.file_path = file_path
        self.relative_path = relative_path
        self.file_hash = file_hash
        self.is_init = is_init
        self.is_extension = is_extension
        self.ast_tree = ast_tree
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "file_path": str(self.file_path),
            "relative_path": self.relative_path,
            "file_hash": self.file_hash,
            "is_init": self.is_init,
            "is_extension": self.is_extension,
            "has_ast": self.ast_tree is not None,
            "error": self.error,
        }

def _hash_and_parse_file(args: Tuple[str, str, str]) -> Dict[str, Any]:
    """Worker function for parallel processing."""
    module_name, file_path_str, rel_path = args
    file_path = Path(file_path_str)
    
    try:
        content_bytes = file_path.read_bytes()
        file_hash = hashlib.sha256(content_bytes).hexdigest()
    except Exception as e:
        return {
            "module_name": module_name,
            "file_path": str(file_path),
            "relative_path": rel_path,
            "file_hash": "",
            "is_init": file_path.name == "__init__.py",
            "is_extension": file_path.suffix in (".so", ".pyd", ".dylib"),
            "ast_tree": None,
            "error": f"Read error: {e}",
        }

    is_extension = file_path.suffix in (".so", ".pyd", ".dylib")
    is_init = file_path.name == "__init__.py"

    if is_extension:
        return {
            "module_name": module_name,
            "file_path": str(file_path),
            "relative_path": rel_path,
            "file_hash": file_hash,
            "is_init": is_init,
            "is_extension": True,
            "ast_tree": None,
            "error": None,
        }

    try:
        source_text = content_bytes.decode("utf-8", errors="replace")
        tree = ast.parse(source_text, filename=str(file_path))
        return {
            "module_name": module_name,
            "file_path": str(file_path),
            "relative_path": rel_path,
            "file_hash": file_hash,
            "is_init": is_init,
            "is_extension": False,
            "ast_tree": tree,
            "error": None,
        }
    except Exception as e:
        return {
            "module_name": module_name,
            "file_path": str(file_path),
            "relative_path": rel_path,
            "file_hash": file_hash,
            "is_init": is_init,
            "is_extension": False,
            "ast_tree": None,
            "error": f"AST parse error: {e}",
        }

class PackageScanner:
    def __init__(self, package_name_or_path: str):
        self.package_name_or_path = package_name_or_path
        self.package_root, self.package_name = self._resolve_package_root(package_name_or_path)

    def _resolve_package_root(self, target: str) -> Tuple[Path, str]:
        path_target = Path(target)
        if path_target.exists():
            if path_target.is_file() and path_target.name == "__init__.py":
                return path_target.parent, path_target.parent.name
            elif path_target.is_dir():
                pkg_name = path_target.name
                if (path_target / "__init__.py").exists():
                    return path_target, pkg_name
                return path_target, pkg_name

        # Resolve installed package via importlib
        try:
            spec = importlib.util.find_spec(target)
            if spec and spec.submodule_search_locations:
                pkg_path = Path(spec.submodule_search_locations[0])
                return pkg_path, target
            elif spec and spec.origin:
                origin_path = Path(spec.origin)
                return origin_path.parent, target
        except Exception:
            pass

        raise ValueError(f"Could not resolve package or directory path for '{target}'")

    def scan(self, max_workers: int = 4) -> Dict[str, ModuleFileInfo]:
        """
        Scans all modules within the package root.
        """
        tasks = []
        for root, dirs, files in os.walk(self.package_root):
            # Exclude __pycache__ and hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            rel_dir = Path(root).relative_to(self.package_root)

            for f in files:
                if f.startswith(".") or not (f.endswith(".py") or f.endswith((".so", ".pyd", ".dylib"))):
                    continue

                file_path = Path(root) / f
                if rel_dir == Path("."):
                    if f == "__init__.py":
                        mod_name = self.package_name
                    else:
                        stem = Path(f).stem.split(".")[0]
                        mod_name = f"{self.package_name}.{stem}"
                else:
                    parts = list(rel_dir.parts)
                    if f == "__init__.py":
                        mod_name = f"{self.package_name}." + ".".join(parts)
                    else:
                        stem = Path(f).stem.split(".")[0]
                        mod_name = f"{self.package_name}." + ".".join(parts) + f".{stem}"

                rel_path = str(file_path.relative_to(self.package_root))
                tasks.append((mod_name, str(file_path), rel_path))

        results: Dict[str, ModuleFileInfo] = {}

        if max_workers > 1 and len(tasks) > 5:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                for res in executor.map(_hash_and_parse_file, tasks):
                    info = ModuleFileInfo(
                        module_name=res["module_name"],
                        file_path=Path(res["file_path"]),
                        relative_path=res["relative_path"],
                        file_hash=res["file_hash"],
                        is_init=res["is_init"],
                        is_extension=res["is_extension"],
                        ast_tree=res["ast_tree"],
                        error=res["error"],
                    )
                    results[info.module_name] = info
        else:
            for task in tasks:
                res = _hash_and_parse_file(task)
                info = ModuleFileInfo(
                    module_name=res["module_name"],
                    file_path=Path(res["file_path"]),
                    relative_path=res["relative_path"],
                    file_hash=res["file_hash"],
                    is_init=res["is_init"],
                    is_extension=res["is_extension"],
                    ast_tree=res["ast_tree"],
                    error=res["error"],
                )
                results[info.module_name] = info

        return results
