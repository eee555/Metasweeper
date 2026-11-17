"""Compile the translation catalogs shipped with built-in plugins."""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en_US", "de_DE", "ja_JP", "pl_PL")


def qt_tool(tool: str) -> Path:
    name = f"pyside6-{tool}" + (".exe" if sys.platform == "win32" else "")
    python_dir = Path(sys.executable).parent
    candidates = [python_dir / name, python_dir / "Scripts" / name,
                  python_dir.parent / "bin" / name]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        found = shutil.which(name)
        if found is None:
            raise FileNotFoundError(f"Qt translation tool not found: {name}")
        executable = Path(found)
    return executable


def validate_catalog(source: Path) -> None:
    tree = ET.parse(source)
    for message in tree.findall('.//message'):
        translation = message.find('translation')
        if (translation is None or translation.get('type') in ('unfinished', 'vanished', 'obsolete')
                or not ''.join(translation.itertext()).strip()):
            raise ValueError(f"Incomplete plugin translation in {source}: {message.findtext('source')}")


def main() -> None:
    from audit_plugin_translations import CONTEXTS

    executable = qt_tool('lrelease')
    directories = {ROOT / 'src/plugins' / name / 'translations' for name in CONTEXTS}
    directories.update(path for path in (ROOT / 'src/plugins').glob('*/translations') if path.is_dir())
    sources = [directory / f'{locale}.ts' for directory in sorted(directories) for locale in LOCALES]
    # Validate all catalogs before producing any output.
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Plugin translation catalog not found: {source}")
        validate_catalog(source)
    for source in sources:
        subprocess.run([str(executable), str(source), '-nounfinished',
                        '-qm', str(source.with_suffix('.qm'))], check=True)


if __name__ == "__main__":
    main()
