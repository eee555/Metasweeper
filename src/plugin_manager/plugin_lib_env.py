"""插件依赖库目录支持

插件管理器无法预打包所有第三方库。用户可指定一个外部目录：

- 普通库目录（``pip install --target`` 的目标）
- 虚拟环境目录（自动识别其中的 ``site-packages``）

加载插件前把该目录追加到 ``sys.path``，插件即可正常 ``import``。
目录为空或不存在时，可用本机同版本解释器自动创建虚拟环境。
"""
from __future__ import annotations

import importlib
import json
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from importlib import metadata
from importlib.machinery import PathFinder
from pathlib import Path
from tempfile import NamedTemporaryFile

import loguru

logger = loguru.logger.bind(name="PluginLibEnv")

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_VENV_TIMEOUT = 300
_PIP_TIMEOUT = 600
_BOOTSTRAP_LOCK = threading.Lock()
_DEBUGPY_REQUIREMENT = "debugpy>=1.8.20"
_TARGET_INSTALL_ERROR = (
    "Upgrading individual packages is disabled for ordinary library directories "
    "because shared namespace packages could be damaged; use a virtual environment."
)


@dataclass
class BootstrapResult:
    """Outcome of preparing the shared plugin dependency environment."""

    library_path: Path | None
    python_executable: Path | None
    errors: list[str] = field(default_factory=list)

_PROBE_CODE = (
    "import sys, struct;"
    "print(sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8)"
)


def current_python_tag() -> tuple[int, int, int]:
    """当前解释器的 (主版本, 次版本, 位数)"""
    return (sys.version_info[0], sys.version_info[1], struct.calcsize("P") * 8)


def python_tag_text() -> str:
    """当前解释器标签，用于界面提示"""
    major, minor, bits = current_python_tag()
    return f"Python {major}.{minor} ({bits} 位)"


def _probe_python(exe: str) -> tuple[int, int, int] | None:
    """探测解释器版本与位数，失败返回 None"""
    try:
        proc = subprocess.run(
            [exe, "-c", _PROBE_CODE],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    parts = proc.stdout.split()
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _candidate_interpreters() -> list[str]:
    """收集可能匹配的解释器路径（去重前）"""
    major, minor, _ = current_python_tag()
    candidates: list[str] = []

    # 开发环境可能运行在 venv 中；优先使用其基础解释器。
    if not getattr(sys, "frozen", False) and "__compiled__" not in globals():
        base_executable = getattr(sys, "_base_executable", None)
        if base_executable:
            candidates.append(base_executable)
        candidates.append(sys.executable)

    for name in (f"python{major}.{minor}", f"python{major}", "python3", "python"):
        exe = shutil.which(name)
        if exe:
            candidates.append(exe)

    launcher = shutil.which("py")
    if launcher:
        try:
            proc = subprocess.run(
                [launcher, f"-{major}.{minor}", "-c",
                 "import sys;print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=_CREATE_NO_WINDOW,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                candidates.append(proc.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass

    if sys.platform == "win32":
        for base in (
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
        ):
            if not base:
                continue
            candidates.append(
                str(Path(base) / "Programs" / "Python"
                    / f"Python{major}{minor}" / "python.exe"))
            candidates.append(
                str(Path(base) / f"Python{major}{minor}" / "python.exe"))

    return candidates


def _is_global_python(exe: str) -> bool:
    """通过解释器自身的前缀判断，避免把虚拟环境误认作全局 Python。"""
    try:
        proc = subprocess.run(
            [exe, "-c", "import sys;print(int(sys.prefix == sys.base_prefix))"],
            capture_output=True, text=True, timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "1"
    except (OSError, subprocess.SubprocessError):
        return False


def find_matching_python() -> str | None:
    """查找版本和位数匹配的全局 Python，拒绝虚拟环境。"""
    want = current_python_tag()
    seen: set[str] = set()
    for exe in _candidate_interpreters():
        try:
            key = os.path.normcase(os.path.abspath(exe))
        except (OSError, ValueError):
            continue
        if key in seen:
            continue
        seen.add(key)
        if _probe_python(exe) == want and _is_global_python(exe):
            return exe
    return None


def is_venv_dir(path: Path) -> bool:
    """判断目录是否为虚拟环境"""
    return (path / "pyvenv.cfg").is_file()


def venv_site_packages(venv_dir: Path) -> Path | None:
    """返回虚拟环境的 site-packages 目录（不存在则 None）"""
    major, minor, _ = current_python_tag()
    if sys.platform == "win32":
        candidate = venv_dir / "Lib" / "site-packages"
    else:
        candidate = venv_dir / "lib" / f"python{major}.{minor}" / "site-packages"
    return candidate if candidate.is_dir() else None


def list_installed_packages(directory: Path) -> list[tuple[str, str]]:
    """仅列出指定 venv 或库目录内带发行包元数据的包。"""
    directory = Path(directory).expanduser()
    if is_venv_dir(directory):
        site = venv_site_packages(directory)
        if site is None:
            raise ValueError("虚拟环境不完整，未找到 site-packages")
    elif directory.is_dir():
        site = directory
    else:
        raise ValueError("依赖目录不存在或不是目录")
    packages = []
    for dist in metadata.distributions(path=[str(site)]):
        try:
            name, version = dist.metadata.get("Name"), dist.version
            if name and version:
                packages.append((name, version))
        except (OSError, ValueError, UnicodeError):
            logger.warning(f"无法读取发行包元数据: {dist}")
    return sorted(packages, key=lambda item: (item[0].casefold(), item[1]))


def venv_python_executable(venv_dir: Path) -> Path:
    """返回虚拟环境的 Python 解释器路径"""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def create_venv(target: Path, python_exe: str) -> None:
    """用指定解释器在 target 创建虚拟环境"""
    target.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [python_exe, "-m", "venv", str(target)],
        capture_output=True,
        text=True,
        timeout=_VENV_TIMEOUT,
        creationflags=_CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or "虚拟环境创建失败")


def resolve_lib_path(path: str) -> tuple[Path | None, str]:
    """解析已配置的目录，不产生副作用

    Returns:
        (可加入 sys.path 的目录, 说明文案)；无法使用时目录为 None
    """
    raw = (path or "").strip()
    if not raw:
        return None, ""

    target = Path(raw).expanduser()
    if is_venv_dir(target):
        site = venv_site_packages(target)
        if site is None:
            return None, "虚拟环境不完整，未找到 site-packages"
        executable = venv_python_executable(target)
        if not executable.is_file():
            return None, "虚拟环境不完整，未找到 Python 解释器"
        if _probe_python(str(executable)) != current_python_tag():
            return None, f"虚拟环境解释器与当前 {python_tag_text()} 不匹配"
        return site, f"使用虚拟环境: {target}"

    if target.exists() and not target.is_dir():
        return None, "所选路径不是目录"
    if target.is_dir():
        return target, f"使用库目录: {target}"
    return None, "目录不存在"


def prepare_lib_dir(path: str) -> tuple[Path | None, str]:
    """解析目录；为空目录或不存在时自动创建虚拟环境

    供设置界面调用，可能耗时数秒。
    """
    raw = (path or "").strip()
    if not raw:
        return None, ""

    target = Path(raw).expanduser()
    if is_venv_dir(target):
        return resolve_lib_path(raw)

    if target.exists() and not target.is_dir():
        return None, "所选路径不是目录"

    if target.is_dir() and any(target.iterdir()):
        return target, f"使用库目录: {target}"

    python_exe = find_matching_python()
    if python_exe is None:
        return None, (
            f"未找到与当前 {python_tag_text()} 匹配的解释器，无法创建虚拟环境"
        )

    try:
        create_venv(target, python_exe)
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        return None, f"创建虚拟环境失败: {e}"

    site = venv_site_packages(target)
    if site is None:
        return None, "虚拟环境创建后未找到 site-packages"
    return site, f"已创建虚拟环境: {target}"


def apply_plugin_lib_dir(path: str) -> Path | None:
    """把配置的依赖库目录追加到 sys.path（启动时调用）"""
    target, message = resolve_lib_path(path)
    if target is None:
        if message:
            logger.warning(f"插件依赖库目录不可用: {message}")
        return None

    text = str(target)
    if text not in sys.path:
        sys.path.append(text)
    logger.info(f"插件依赖库目录已加入 sys.path: {text}")
    return target


def _python_for_library(target: Path, is_venv: bool) -> Path | None:
    if is_venv:
        candidate = venv_python_executable(target)
        return candidate if candidate.is_file() else None
    matching = find_matching_python()
    return Path(matching) if matching else None


def _append_import_path(path: Path) -> None:
    text = str(path)
    if text not in sys.path:
        sys.path.append(text)
    importlib.invalidate_caches()


def _pip_command(
    python_executable: Path,
    requirements_file: Path,
    *,
    target: Path | None = None,
    index_urls: list[str] | None = None,
) -> list[str]:
    command = [str(python_executable), "-m", "pip", "install"]
    if target is not None:
        command.extend(("--target", str(target)))
    if index_urls:
        command.extend(("--index-url", index_urls[0]))
        for url in index_urls[1:]:
            command.extend(("--extra-index-url", url))
    command.extend((
        "--upgrade", "--no-input", "--disable-pip-version-check",
        "--progress-bar", "raw", "--timeout", "20", "--retries", "1",
        "-r", str(requirements_file),
    ))
    return command


def _stream_install(command: list[str], label: str,
                    output_callback: Callable[[str], None]) -> str | None:
    """Stream merged pip output while retaining the installation timeout."""
    try:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=_CREATE_NO_WINDOW,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
    except OSError as exc:
        return f"{label}: {exc}"

    assert proc.stdout is not None
    output: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        finally:
            output.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + _PIP_TIMEOUT
    recent: deque[str] = deque(maxlen=100)
    finished = False
    timed_out = False
    while not finished:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proc.kill()
            timed_out = True
            break
        try:
            line = output.get(timeout=min(0.2, remaining))
        except queue.Empty:
            continue
        if line is None:
            finished = True
        else:
            recent.append(line)
            output_callback(line.rstrip("\r\n"))
    proc.wait()
    reader.join(timeout=1)
    proc.stdout.close()
    if timed_out:
        return f"{label} timed out"
    if proc.returncode != 0:
        return "".join(recent).strip() or f"{label}: pip exited with status {proc.returncode}"
    return None


def _run_install(command: list[str], label: str,
                 output_callback: Callable[[str], None] | None = None) -> str | None:
    logger.info(f"{label} started")
    if output_callback is not None:
        return _stream_install(command, label, output_callback)
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_PIP_TIMEOUT,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        output_parts = []
        for part in (exc.stdout, exc.stderr):
            if isinstance(part, bytes):
                part = part.decode(errors="replace")
            if part and str(part).strip():
                output_parts.append(str(part).strip())
        detail = "\n".join(output_parts) or str(exc)
        logger.error(f"{label} timed out: {detail}")
        return f"{label} timed out: {detail}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{label}: {exc}"
    if proc.returncode == 0:
        if proc.stdout.strip():
            logger.info(f"{label}: {proc.stdout.strip()}")
        return None
    output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part.strip())
    detail = output or f"pip exited with status {proc.returncode}"
    logger.error(f"{label}: {detail}")
    return f"{label}: {detail}"


def _has_debugpy(library_path: Path) -> bool:
    return PathFinder.find_spec("debugpy", [str(library_path)]) is not None


def _environment_for_directory(
    configured: str, errors: list[str],
) -> tuple[Path | None, Path | None, bool]:
    configured = configured.strip()
    if not configured:
        errors.append(
            "未配置插件依赖目录；设置中显示的默认目录仅为建议，"
            "请选择已有目录或创建虚拟环境后点击“确定”保存。"
        )
        return None, None, False
    target = Path(configured).expanduser().resolve()

    if is_venv_dir(target):
        library_path = venv_site_packages(target)
        python_executable = _python_for_library(target, True)
        if library_path is None:
            errors.append(f"Plugin venv is incomplete: site-packages not found in {target}")
        if python_executable is None:
            errors.append(f"Plugin venv is incomplete: Python executable not found in {target}")
        elif _probe_python(str(python_executable)) != current_python_tag():
            errors.append(
                f"Plugin venv interpreter does not match {python_tag_text()}: "
                f"{python_executable}")
            return library_path, None, False
        return library_path, python_executable, False

    if target.exists() and not target.is_dir():
        errors.append(f"Plugin dependency path is not a directory: {target}")
        return None, None, False
    if not target.is_dir():
        errors.append(f"Configured plugin dependency directory does not exist: {target}")
        return None, None, False

    # Existing non-venv directories are pip --target environments.
    python_executable = _python_for_library(target, False)
    if python_executable is None:
        errors.append(f"No matching external Python is available to manage libraries in {target}")
        return target, None, True
    return target, python_executable, True


def _ensure_environment(data_dir: Path, errors: list[str]) -> tuple[Path | None, Path | None, bool]:
    from .settings_manager import SettingsManager

    return _environment_for_directory(SettingsManager(data_dir).plugin_lib_dir, errors)


def prepare_plugin_dependency_environment(data_dir: Path) -> BootstrapResult:
    """Prepare and add the configured library environment without installing packages."""
    errors: list[str] = []
    data_dir = Path(data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return BootstrapResult(None, None, [f"Could not create data directory: {exc}"])

    with _BOOTSTRAP_LOCK:
        library_path, python_executable, _ = _ensure_environment(data_dir, errors)
        if library_path is not None and python_executable is not None:
            _append_import_path(library_path)
            logger.info(f"Plugin dependency environment ready at {library_path}")
        return BootstrapResult(library_path, python_executable, errors)


def _install_requirements_file(
    data_dir: Path,
    requirements_file: Path,
    label: str,
    output_callback: Callable[[str], None] | None = None,
) -> str | None:
    requirements_file = Path(requirements_file)
    if not requirements_file.is_file():
        return f"Requirements file not found: {requirements_file}"

    errors: list[str] = []
    data_dir = Path(data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Could not create data directory: {exc}"

    with _BOOTSTRAP_LOCK:
        library_path, python_executable, use_target = _ensure_environment(data_dir, errors)
        if library_path is None or python_executable is None:
            return "; ".join(errors) or "Plugin dependency environment is unavailable"
        _append_import_path(library_path)
        from .settings_manager import SettingsManager
        index_urls = SettingsManager(data_dir).plugin_pip_indexes
        error = _run_install(
            _pip_command(
                python_executable,
                requirements_file,
                target=library_path if use_target else None,
                index_urls=index_urls,
            ),
            label,
            output_callback,
        )
        if error:
            return error
        importlib.invalidate_caches()
        return None


def _package_name_key(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", name):
        raise ValueError(f"Invalid distribution name: {name!r}")
    return re.sub(r"[-_.]+", "-", name).lower()


def _index_arguments(index_urls: list[str]) -> list[str]:
    from .settings_manager import normalize_pip_indexes

    indexes = normalize_pip_indexes(index_urls)
    if not indexes:
        return []
    args = ["--index-url", indexes[0]]
    for url in indexes[1:]:
        args.extend(("--extra-index-url", url))
    return args


def check_package_updates(directory: Path, index_urls: list[str]) -> dict[str, str]:
    """Return normalized distribution names and latest compatible versions.

    This performs network I/O and must not run on the GUI thread. A failed
    lookup raises an exception; an empty result means no updates were found.
    """
    indexes = _index_arguments(index_urls)
    errors: list[str] = []
    library_path, executable, _ = _environment_for_directory(str(directory), errors)
    if library_path is None or executable is None:
        raise RuntimeError("; ".join(errors) or "Plugin dependency environment is unavailable")
    # A network lookup may outlive its dialog. Do not hold the installation lock;
    # concurrent changes can make the returned package list a stale snapshot.
    command = [str(executable), "-m", "pip", "list", "--outdated", "--format=json",
               "--path", str(library_path), "--disable-pip-version-check",
               "--no-input", "--timeout", "20", "--retries", "1", *indexes]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120,
                              creationflags=_CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Package update check timed out") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Package update check failed: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()
                           or f"pip exited with status {proc.returncode}")
    # pip list can exit successfully with [] even when an index is unreachable.
    # A retry means its results may be incomplete, including with extra indexes.
    if "WARNING: Retrying" in proc.stderr or "Could not fetch URL" in proc.stderr:
        raise RuntimeError(f"Package update check incomplete: {proc.stderr.strip()}")
    try:
        data = json.loads(proc.stdout)
        if not isinstance(data, list):
            raise ValueError("expected a list")
        result: dict[str, str] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("expected a package object")
            name, version = item.get("name"), item.get("latest_version")
            if not isinstance(name, str) or not isinstance(version, str) or not version:
                raise ValueError("missing package name or latest version")
            result[_package_name_key(name)] = version
        return result
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"Invalid package update response: {exc}") from exc


def check_package_updates_async(directory: Path, index_urls: list[str]) -> Future[dict[str, str]]:
    """Check in a background thread; Future callbacks run outside the GUI thread."""
    future: Future[dict[str, str]] = Future()
    directory_snapshot, indexes_snapshot = Path(directory), list(index_urls)

    def run() -> None:
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(check_package_updates(directory_snapshot, indexes_snapshot))
        except Exception as exc:
            future.set_exception(exc)

    threading.Thread(target=run, name="plugin-package-update-check", daemon=True).start()
    return future


def upgrade_installed_package(
    directory: Path, index_urls: list[str], name: str, *,
    output_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Upgrade one installed distribution; return an error or None on success.

    Run this from an installation worker, as with install_plugin_requirements.
    """
    try:
        name_key = _package_name_key(name)
        indexes = _index_arguments(index_urls)
        with _BOOTSTRAP_LOCK:
            errors: list[str] = []
            library_path, executable, use_target = _environment_for_directory(str(directory), errors)
            if use_target:
                return _TARGET_INSTALL_ERROR
            if library_path is None or executable is None:
                return "; ".join(errors) or "Plugin dependency environment is unavailable"
            installed = {_package_name_key(package) for package, _ in list_installed_packages(library_path)
                         if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", package)}
            if name_key not in installed:
                return f"Distribution is not installed in the selected environment: {name}"
            command = [str(executable), "-m", "pip", "install"]
            command.extend((*indexes, "--upgrade", "--no-input", "--disable-pip-version-check",
                            "--progress-bar", "raw", "--timeout", "20", "--retries", "1",
                            "--", name))
            error = _run_install(command, f"Upgrading {name}", output_callback)
            if error is None:
                importlib.invalidate_caches()
            return error
    except (OSError, ValueError) as exc:
        return str(exc)


def install_plugin_requirements(
    data_dir: Path, requirements_file: Path, *,
    output_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Install one plugin's dependencies after an explicit user action."""
    return _install_requirements_file(
        data_dir, requirements_file, "Manually installing plugin dependencies",
        output_callback)


def install_debugpy(
    data_dir: Path, *, output_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Install debugpy only after the user explicitly requests debugging."""
    errors: list[str] = []
    data_dir = Path(data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Could not create data directory: {exc}"

    with _BOOTSTRAP_LOCK:
        library_path, python_executable, use_target = _ensure_environment(data_dir, errors)
        if library_path is None or python_executable is None:
            return "; ".join(errors) or "Plugin dependency environment is unavailable"
        _append_import_path(library_path)
        if _has_debugpy(library_path):
            return None

        from .settings_manager import SettingsManager
        index_urls = SettingsManager(data_dir).plugin_pip_indexes
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as stream:
            stream.write(_DEBUGPY_REQUIREMENT + "\n")
            requirements_file = Path(stream.name)
        try:
            error = _run_install(
                _pip_command(
                    python_executable,
                    requirements_file,
                    target=library_path if use_target else None,
                    index_urls=index_urls,
                ),
                "Manually installing debugpy",
                output_callback,
            )
            if error is None:
                importlib.invalidate_caches()
            return error
        finally:
            requirements_file.unlink(missing_ok=True)
