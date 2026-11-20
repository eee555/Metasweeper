"""Track manager-installed distributions and plan reversible plugin removal."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import site
import stat
import threading
import sysconfig
from dataclasses import dataclass, replace
from typing import Callable
from importlib import metadata
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp

from loguru import logger
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from PySide6.QtCore import QCoreApplication

from .app_paths import get_all_plugin_dirs, get_executable_dir
from .plugin_catalog import LOCAL_ZIP_SOURCE, META_FILENAME, read_installed_metadata, read_installed_plugin
from .plugin_download import is_plain_plugin_directory


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginManagerWindow", text)


def _ledger_path(data_dir: Path, library: Path) -> Path:
    key = hashlib.sha256(os.fsencode(os.path.normcase(str(library.resolve())))).hexdigest()
    return data_dir / f"plugin-dependencies-{key}.json"


def _ledger(data_dir: Path, library: Path) -> dict:
    try:
        value = json.loads(_ledger_path(data_dir, library).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logger.warning("Could not read dependency ownership for {}", library)
        return {}


def _inventory(library: Path) -> dict[str, list[metadata.Distribution]]:
    result: dict[str, list[metadata.Distribution]] = {}
    for dist in metadata.distributions(path=[str(library)]):
        name = dist.metadata.get("Name")
        if name:
            result.setdefault(canonicalize_name(name), []).append(dist)
    return result


def _fingerprint(dist: metadata.Distribution) -> str:
    record = dist.read_text("RECORD")
    if not record:
        return ""
    record_file = next((item for item in dist.files or ()
                        if item.name == "RECORD" and item.parent.name.endswith(".dist-info")), None)
    if record_file is None:
        return ""
    info = Path(dist.locate_file(record_file)).stat()
    identity = f"{dist.version}\n{info.st_mtime_ns}\n{info.st_ino}\n{record}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def installed_fingerprints(library: Path) -> dict[str, str]:
    return {name: _fingerprint(entries[0]) if len(entries) == 1 else ""
            for name, entries in _inventory(library).items()}


def record_install(data_dir: Path, library: Path, before: dict[str, str]) -> None:
    """Claim newly installed packages and retain ownership across plugin-driven upgrades."""
    records = _ledger(data_dir, library)
    for name, entries in _inventory(library).items():
        if len(entries) != 1:
            records.pop(name, None)
            continue
        fingerprint = _fingerprint(entries[0])
        previous = before.get(name)
        if fingerprint and (name not in before or (previous and records.get(name) == previous)):
            records[name] = fingerprint
        else:
            records.pop(name, None)
    _write_json(_ledger_path(data_dir, library), records)


def _write_json(target: Path, value: dict) -> None:
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False)
        except BaseException:
            stream.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def is_managed_plugin(package: Path) -> bool:
    root = get_executable_dir() / "user_plugins"
    return (package.parent.resolve() == root.resolve()
            and is_plain_plugin_directory(root)
            and not package.name.startswith("_")
            and is_plain_plugin_directory(package)
            and (read_installed_plugin(package) is not None
                 or ((package / "__init__.py").is_file()
                     and read_installed_metadata(package).get("source") == LOCAL_ZIP_SOURCE)))


def _requirements(package: Path) -> set[str]:
    try:
        content = (package / "requirements.txt").read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return set()
    result = set()
    for raw in content.splitlines():
        line = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
        if line and not line.startswith("#"):
            req = Requirement(line)
            if req.marker is None or req.marker.evaluate():
                result.add(canonicalize_name(req.name))
    return result


def _closure(roots: set[str], graph: dict[str, set[str]]) -> set[str]:
    seen = set()
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo.extend(graph.get(name, ()))
    return seen


def _files(dist: metadata.Distribution, library: Path, scripts: Path | None) -> set[Path]:
    if dist.files is None:
        raise ValueError(_tr("Missing distribution file list"))
    paths = set()
    script_names = {entry.name for entry in dist.entry_points
                    if entry.group in {"console_scripts", "gui_scripts"}}
    launchers = {path for name in script_names
                 for path in (name, name + ".exe", name + "-script.py", name + "-script.pyw")}
    for item in dist.files:
        original = Path(os.path.abspath(dist.locate_file(item)))
        if not ((original != library and original.is_relative_to(library))
                or (scripts is not None and original.parent == scripts
                    and original.name in launchers
                    and not re.fullmatch(r"pythonw?[\d.]*(?:\.exe)?", original.name, re.I))):
            raise ValueError(_tr("Distribution lists files outside its environment"))
        # Never traverse symlinks or junctions when moving files.
        current = original
        while current not in (library, scripts):
            try:
                info = current.lstat()
            except FileNotFoundError:
                pass
            else:
                if (stat.S_ISLNK(info.st_mode)
                        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                    raise ValueError(_tr("Distribution lists a linked path"))
                if current == original and not stat.S_ISREG(info.st_mode):
                    raise ValueError(_tr("Distribution lists a non-file path"))
            current = current.parent
        paths.add(original)
    return paths


@dataclass(frozen=True)
class RemovalPlan:
    package: Path
    library: Path | None = None
    packages: tuple[tuple[str, str], ...] = ()
    files: tuple[Path, ...] = ()
    kept: tuple[str, ...] = ()
    note: str = ""
    release: str = ""
    include_unrecorded: bool = False


def _make_plan(package: Path, data_dir: Path, library: Path, scripts: Path | None, *,
               include_unrecorded: bool) -> RemovalPlan:
    inventory = _inventory(library)
    records = _ledger(data_dir, library)
    graph: dict[str, set[str]] = {}
    owned = set()
    for name, entries in inventory.items():
        edges = graph[name] = set()
        for dist in entries:
            for raw in dist.requires or ():
                req = Requirement(raw)
                # Optional dependencies count too: metadata cannot tell which extras were requested.
                if req.marker is None or any(
                    req.marker.evaluate({"extra": extra})
                    for extra in ("", *(dist.metadata.get_all("Provides-Extra") or ()))
                ):
                    edges.add(canonicalize_name(req.name))
        record = records.get(name)
        if len(entries) == 1 and record and record == _fingerprint(entries[0]):
            owned.add(name)

    selected = _closure(_requirements(package), graph) & inventory.keys()
    candidates = owned
    if include_unrecorded:
        # An explicitly selected plugin library can still be the app's own
        # site-packages. Legacy packages there have no safe ownership boundary.
        runtime_paths = {Path(sysconfig.get_path(key)).resolve() for key in ("purelib", "platlib")}
        user_site = site.getusersitepackages()
        if user_site:
            runtime_paths.add(Path(user_site).resolve())
        if library not in runtime_paths:
            candidates = owned | {
                name for name in selected
                if len(inventory[name]) == 1 and _fingerprint(inventory[name][0])
            }
    roots = set(inventory) - (selected & candidates)
    for directory in {*get_all_plugin_dirs(), package.parent}:
        if not directory.is_dir():
            continue
        for other in directory.iterdir():
            if (other.resolve() != package and not other.name.startswith("_")
                    and (other / "__init__.py").is_file()):
                roots.update(_requirements(other))
    removable = selected - _closure(roots, graph)
    if not removable:
        return RemovalPlan(package, library, kept=tuple(sorted(selected)))

    claims: dict[Path, set[str]] = {}
    unsafe = set()
    for name, entries in inventory.items():
        for dist in entries:
            try:
                paths = _files(dist, library, scripts)
            except (ValueError, OSError):
                if name not in removable:
                    # Without its file list we cannot rule out overlap with retained packages.
                    return RemovalPlan(package, library, kept=tuple(sorted(selected)),
                                       note=_tr("无法完整核对已安装包的文件清单，已保留共享环境中的包。"))
                unsafe.add(name)
            else:
                for path in paths:
                    claims.setdefault(path, set()).add(name)

    while True:
        blocked = unsafe | {name for names in claims.values() if names - removable for name in names}
        remaining = removable - _closure(blocked, graph)
        if remaining == removable:
            break
        removable = remaining
    return RemovalPlan(
        package, library,
        tuple((name, inventory[name][0].version) for name in sorted(removable)),
        tuple(sorted(path for path, names in claims.items() if names <= removable)),
        tuple(sorted(selected - removable)),
    )


def plan_removal(package: Path, data_dir: Path, *, include_unrecorded: bool = False) -> RemovalPlan:
    from .plugin_lib_env import _BOOTSTRAP_LOCK, _ensure_environment

    with _BOOTSTRAP_LOCK:
        if not is_managed_plugin(package):
            raise ValueError(_tr("只支持卸载由管理器安装的用户插件。"))
        package = package.resolve()
        release = hashlib.sha256((package / META_FILENAME).read_bytes()).hexdigest()
        errors: list[str] = []
        library, python, use_target = _ensure_environment(data_dir, errors)
        if library is None or python is None:
            return RemovalPlan(package, note=_tr("无法读取插件依赖环境，卸载时会保留其中的包。"),
                               release=release, include_unrecorded=include_unrecorded)
        library = library.resolve()
        try:
            scripts = None if use_target else python.parent.resolve()
            result = _make_plan(package, data_dir, library, scripts,
                                include_unrecorded=include_unrecorded)
            return replace(result, release=release, include_unrecorded=include_unrecorded)
        except (InvalidRequirement, OSError, UnicodeError, ValueError) as exc:
            logger.warning("Could not plan dependency cleanup: {}", exc)
            return RemovalPlan(package, library, note=_tr("无法确认依赖关系，已保留共享环境中的包。"),
                               release=release, include_unrecorded=include_unrecorded)


def remove_plugin(plan: RemovalPlan, data_dir: Path, *, progress: Callable[[int, int], None] | None = None) -> None:
    from .plugin_lib_env import _BOOTSTRAP_LOCK

    with _BOOTSTRAP_LOCK:
        if plan_removal(plan.package, data_dir, include_unrecorded=plan.include_unrecorded) != plan:
            raise RuntimeError(_tr("插件或依赖环境已变化，请重新确认卸载。"))
        backups = []
        moved: list[tuple[Path, Path]] = []
        rollback_failed = False
        try:
            plugin_backup = Path(mkdtemp(prefix="_uninstall_", dir=plan.package.parent))
            backups.append(plugin_backup)
            if plan.files:
                assert plan.library is not None
                dependency_backup = Path(mkdtemp(prefix="_uninstall_", dir=plan.library))
                backups.append(dependency_backup)
            file_count = len(plan.files)
            if progress is not None and file_count:
                progress(0, file_count)
            for index, source in enumerate(plan.files):
                    if source.exists():
                        target = dependency_backup / str(index)
                        source.rename(target)
                        moved.append((source, target))
                    if progress is not None:
                        progress(index + 1, file_count)
            target = plugin_backup / plan.package.name
            plan.package.rename(target)
            moved.append((plan.package, target))
            if plan.packages:
                assert plan.library is not None
                records = _ledger(data_dir, plan.library)
                for name, _ in plan.packages:
                    records.pop(name, None)
                _write_json(_ledger_path(data_dir, plan.library), records)
        except BaseException:
            failed = []
            for source, target in reversed(moved):
                try:
                    target.rename(source)
                except OSError as exc:
                    failed.append(f"{target} → {source}: {exc}")
            if failed:
                rollback_failed = True
                raise RuntimeError(_tr("部分文件恢复失败，备份仍在原处：\n{files}").format(
                    files="\n".join(failed)))
            raise
        finally:
            # Keep recoverable files if any rollback rename failed.
            if not rollback_failed:
                for directory in backups:
                    try:
                        shutil.rmtree(directory)
                    except OSError:
                        logger.warning("Could not delete uninstall backup: {}", directory)
        if plan.library is not None:
            # Namespace packages may share directories; remove only empty ones.
            parents = {parent for path in plan.files for parent in path.parents
                       if parent != plan.library and parent.is_relative_to(plan.library)}
            for parent in sorted(parents, key=lambda path: len(path.parts), reverse=True):
                try:
                    parent.rmdir()
                except OSError:
                    pass


def _plan_key(plan: RemovalPlan) -> str:
    value = (str(plan.package), str(plan.library), plan.packages,
             tuple(map(str, plan.files)), plan.kept, plan.note, plan.release)
    if plan.include_unrecorded:
        value += ("include_unrecorded",)
    return hashlib.sha256(json.dumps(value).encode("utf-8")).hexdigest()


def queue_removal(plan: RemovalPlan, data_dir: Path) -> None:
    """Retry an approved plan once, before the next process imports plugins."""
    from .plugin_lib_env import _BOOTSTRAP_LOCK

    with _BOOTSTRAP_LOCK:
        if plan_removal(plan.package, data_dir, include_unrecorded=plan.include_unrecorded) != plan:
            raise RuntimeError(_tr("插件或依赖环境已变化，请重新确认卸载。"))
        _write_json(data_dir / "pending-plugin-uninstall.json",
                    {"package": plan.package.name, "plan": _plan_key(plan),
                     "include_unrecorded": plan.include_unrecorded})


def apply_queued_removal(data_dir: Path) -> str:
    request = data_dir / "pending-plugin-uninstall.json"
    try:
        value = json.loads(request.read_text(encoding="utf-8"))
        request.unlink()
    except FileNotFoundError:
        return ""
    except (OSError, ValueError) as exc:
        return f"无法读取待执行的插件卸载操作：{exc}"

    try:
        name = value.get("package") if isinstance(value, dict) else None
        if not isinstance(name, str) or Path(name).name != name or name in {".", ".."}:
            raise ValueError(_tr("无效的插件目录"))
        package = get_executable_dir() / "user_plugins" / name
        plan = plan_removal(package, data_dir,
                            include_unrecorded=value.get("include_unrecorded") is True)
        if _plan_key(plan) != value.get("plan"):
            raise RuntimeError(_tr("插件或依赖环境已变化，请重新确认卸载。"))
        remove_plugin(plan, data_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        return f"重启时未能卸载插件：{exc}"
    return ""


def run_removal_in_thread(
    plan: RemovalPlan,
    data_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    finished_callback: Callable[[BaseException | None], None] | None = None,
) -> "tuple[threading.Thread, Future[str], Callable[[int, int], None]]":
    """Run dependency and package cleanup off the Qt application thread."""
    from concurrent.futures import Future

    future: Future[str] = Future()

    def worker() -> None:
        if not future.set_running_or_notify_cancel():
            return
        exception: BaseException | None = None
        try:
            report = _removal_progress_reporter(
                plan, progress_callback)
            remove_plugin(plan, data_dir, progress=report)
            future.set_result("")
        except BaseException as exc:
            exception = exc
            future.set_exception(exc)
        finally:
            if finished_callback is not None:
                try:
                    finished_callback(exception)
                except BaseException:
                    logger.exception("Could not report plugin uninstall completion")

    thread = threading.Thread(
        target=worker,
        name="plugin-uninstall",
        daemon=True,
    )
    return thread, future, progress_callback or (lambda _completed, _total: None)


def _removal_progress_reporter(
    plan: RemovalPlan,
    progress_callback: Callable[[int, int], None] | None,
) -> Callable[[int, int], None]:
    if progress_callback is None:
        return lambda _completed, _total: None
    maximum = len(plan.files)
    if maximum:
        progress_callback(0, maximum)

    return progress_callback
