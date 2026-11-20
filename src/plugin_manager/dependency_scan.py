"""Read-only dependency diagnostics for plugin packages.

Only PEP 508 requirement lines are evaluated. pip options, included files,
URLs and extras cannot be verified reliably from installed distribution metadata.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QCoreApplication

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import Version

DependencyStatus = Literal["no_requirements", "satisfied", "missing", "conflict", "unknown"]
ItemStatus = Literal["satisfied", "missing", "conflict", "unknown", "skipped"]
ImportStatus = Literal["not_attempted", "loaded", "failed"]


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginManagerWindow", text)


@dataclass(frozen=True)
class DependencyDiagnostic:
    line: int
    requirement: str
    status: ItemStatus
    installed_version: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class PluginDependencyStatus:
    module_name: str
    module_path: Path
    requirements_path: Path | None
    status: DependencyStatus
    diagnostics: tuple[DependencyDiagnostic, ...] = ()
    import_status: ImportStatus = "not_attempted"
    import_error: str | None = None


def scan_plugin_dependencies(module_path: Path, module_name: str) -> PluginDependencyStatus:
    """Inspect a package's requirements without importing or installing anything.

    Single-file plugins have no private requirements file. For a package with no
    requirements file, requirements_path identifies the expected location.
    """
    path = module_path.parent / "requirements.txt" if module_path.name == "__init__.py" else None
    if path is None:
        return PluginDependencyStatus(module_name, module_path, None, "no_requirements")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return PluginDependencyStatus(module_name, module_path, path, "no_requirements")
    except (OSError, UnicodeError) as exc:
        item = DependencyDiagnostic(
            0, "", "unknown", detail=_tr("Cannot read requirements: {error}").format(error=exc))
        return PluginDependencyStatus(module_name, module_path, path, "unknown", (item,))

    items: list[DependencyDiagnostic] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        # A hash starts a pip comment only when preceded by whitespace; URLs can
        # contain fragments, which are kept and marked unknown below.
        line = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement:
            items.append(DependencyDiagnostic(
                line_number, line, "unknown", detail=_tr("Unsupported or invalid requirement")))
            continue
        try:
            if req.marker and not req.marker.evaluate():
                items.append(DependencyDiagnostic(
                    line_number, line, "skipped", detail=_tr("Environment marker does not apply")))
                continue
            if req.url or req.extras:
                items.append(DependencyDiagnostic(
                    line_number, line, "unknown", detail=_tr("Direct URLs and extras cannot be verified")))
                continue
            version = metadata.version(req.name)
            parsed_version = Version(version)
            if req.specifier and not req.specifier.contains(parsed_version, prereleases=None):
                items.append(DependencyDiagnostic(
                    line_number, line, "conflict", version,
                    _tr("Installed version does not satisfy constraint")))
            else:
                items.append(DependencyDiagnostic(line_number, line, "satisfied", version))
        except metadata.PackageNotFoundError:
            # Frozen executables may omit distribution metadata for bundled modules.
            if getattr(sys, "frozen", False) or "__compiled__" in globals():
                items.append(DependencyDiagnostic(
                    line_number, line, "unknown",
                    detail=_tr("Distribution metadata unavailable in packaged application")))
            else:
                items.append(DependencyDiagnostic(
                    line_number, line, "missing", detail=_tr("Distribution metadata not found")))
        except Exception as exc:
            items.append(DependencyDiagnostic(
                line_number, line, "unknown",
                detail=_tr("Cannot verify requirement: {error}").format(error=exc)))

    if not items:
        return PluginDependencyStatus(module_name, module_path, path, "no_requirements")

    statuses = {item.status for item in items}
    overall: DependencyStatus = next((status for status in ("unknown", "conflict", "missing") if status in statuses), "satisfied")  # type: ignore[assignment]
    return PluginDependencyStatus(module_name, module_path, path, overall, tuple(items))
