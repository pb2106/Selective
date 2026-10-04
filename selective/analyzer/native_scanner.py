"""
Native Binary Scanner for Selective.
Scans compiled extensions (.so, .pyd, .dylib) using pyelftools to extract DT_NEEDED dependencies, RPATH, and PyInit symbols.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import re

try:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.dynamic import DynamicSection
    HAS_ELFTOOLS = True
except ImportError:
    HAS_ELFTOOLS = False

class NativeLibraryInfo:
    def __init__(
        self,
        file_path: Path,
        needed_libraries: List[str],
        rpaths: List[str],
        imported_c_modules: List[str],
        is_native: bool = True,
    ):
        self.file_path = file_path
        self.needed_libraries = needed_libraries
        self.rpaths = rpaths
        self.imported_c_modules = imported_c_modules
        self.is_native = is_native

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "needed_libraries": self.needed_libraries,
            "rpaths": self.rpaths,
            "imported_c_modules": self.imported_c_modules,
            "is_native": self.is_native,
        }

class NativeScanner:
    def scan_library(self, file_path: Path) -> NativeLibraryInfo:
        needed: List[str] = []
        rpaths: List[str] = []
        c_modules: List[str] = []

        if not file_path.exists():
            return NativeLibraryInfo(file_path, [], [], [], False)

        # ELF parsing via pyelftools if available
        if HAS_ELFTOOLS and file_path.suffix in (".so", ".dylib"):
            try:
                with open(file_path, "rb") as f:
                    elf = ELFFile(f)
                    for section in elf.iter_sections():
                        if isinstance(section, DynamicSection):
                            for tag in section.iter_tags():
                                if tag.entry.d_tag == "DT_NEEDED":
                                    needed.append(tag.needed)
                                elif tag.entry.d_tag in ("DT_RPATH", "DT_RUNPATH"):
                                    rpaths.append(tag.rpath)
            except Exception:
                pass

        # String scanning for PyImport_ImportModule calls or submodule strings in binary
        try:
            content = file_path.read_bytes()
            # Look for PyInit_<name> or PyImport_ImportModule strings
            pyinit_matches = re.findall(b"PyInit_([A-Za-z0-9_]+)", content)
            for match in pyinit_matches:
                c_modules.append(match.decode("ascii", errors="ignore"))
        except Exception:
            pass

        return NativeLibraryInfo(
            file_path=file_path,
            needed_libraries=needed,
            rpaths=rpaths,
            imported_c_modules=c_modules,
            is_native=True,
        )
