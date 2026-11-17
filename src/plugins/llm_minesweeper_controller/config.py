from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from plugin_sdk import IntConfig, OtherInfoBase
from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("MinesweeperMcp")


CONFIG_IDENTITIES = ("LlmMinesweeperControllerPlugin", "LLM反控扫雷", "元扫雷 MCP 服务")


def valid_port(value: object) -> bool:
    return type(value) is int and 1024 <= value <= 65535


class LlmMinesweeperControllerConfig(OtherInfoBase):
    port = IntConfig(default=8765, label=_translate("MinesweeperMcp", "MCP 端口"), min_value=1024, max_value=65535,
                     validator=lambda value: None if valid_port(value) else _translate("MinesweeperMcp", "端口必须为 1024..65535 的整数"))

    def from_dict(self, data: dict, silent: bool = True) -> None:
        port = data.get("port", 8765) if isinstance(data, dict) else 8765
        super().from_dict(
            {"port": port if valid_port(port) else 8765}, silent=silent)


def sanitize_legacy_configs(data_dir: Path) -> None:
    paths = [data_dir / "config.json"]
    paths.extend(data_dir / name / "config.json" for name in CONFIG_IDENTITIES)
    if data_dir.name in CONFIG_IDENTITIES:
        paths.extend(data_dir.parent / name /
                     "config.json" for name in CONFIG_IDENTITIES)
    for path in paths:
        if (not path.is_file() or path.is_symlink()
                or any(parent.is_symlink() for parent in path.parents)):
            continue
        temporary = None
        try:
            try:
                with path.open(encoding="utf-8") as source:
                    data = json.load(source)
            except (ValueError, UnicodeError):
                data = {}
            port = data.get("port", 8765) if isinstance(data, dict) else 8765
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".mcp-config-", delete=False) as target:
                temporary = Path(target.name)
                json.dump({"port": port if valid_port(port) else 8765}, target)
            os.replace(temporary, path)
        except OSError:
            raise RuntimeError(_translate("MinesweeperMcp", "旧配置清理失败，MCP 服务保持停止")) from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
