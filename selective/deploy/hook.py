"""
Environment Hook Installer/Uninstaller for Selective.
Writes sitecustomize / .pth integration stubs into the active virtual environment.
"""

import sys
import site
from pathlib import Path

HOOK_STUB_CODE = """# Selective sitecustomize hook stub
try:
    from selective.loader.finder import SelectiveFinder
    SelectiveFinder.install()
except Exception:
    pass
"""

class HookInstaller:
    @staticmethod
    def get_site_packages_dir() -> Path:
        site_dirs = site.getsitepackages()
        if site_dirs:
            return Path(site_dirs[0])
        return Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

    @classmethod
    def install_hook(cls) -> Path:
        sp_dir = cls.get_site_packages_dir()
        sp_dir.mkdir(parents=True, exist_ok=True)
        pth_file = sp_dir / "selective.pth"
        pth_file.write_text("import selective.deploy.hook; selective.deploy.hook._on_site_import()\n", encoding="utf-8")
        return pth_file

    @classmethod
    def uninstall_hook(cls) -> bool:
        sp_dir = cls.get_site_packages_dir()
        pth_file = sp_dir / "selective.pth"
        if pth_file.exists():
            pth_file.unlink()
            return True
        return False

def _on_site_import():
    try:
        from selective.loader.finder import SelectiveFinder
        SelectiveFinder.install()
    except Exception:
        pass
