#!/usr/bin/env python
"""
插件创建脚本

用法:
    python create_plugin.py discover
    python create_plugin.py create --name my_plugin --description "描述" [options]

功能:
    - 根据参数生成插件代码
    - 动态读取可用的控制命令和订阅事件
    - 支持单文件和模块化包结构
    - 自动生成订阅代码、控制申请、服务接口
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# 环境检测
# ═══════════════════════════════════════════════════════════════════

def get_base_dir() -> Path:
    """获取基础目录（开发模式）"""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent.parent.parent


def is_frozen() -> bool:
    """检测是否在 PyInstaller 打包环境中"""
    base = get_base_dir()
    return (base / "metaminsweeper.exe").exists()


def get_install_dir() -> Path:
    """获取安装目录"""
    return get_base_dir()


def get_plugins_dir() -> Path:
    """获取插件目录"""
    base = get_install_dir()
    if is_frozen():
        return base / "plugins"
    return base / "src" / "plugins"


def get_shared_types_dir() -> Path:
    """获取 shared_types 目录"""
    base = get_install_dir()
    if is_frozen():
        return base / "shared_types"
    return base / "src" / "shared_types"


def get_plugin_sdk_dir() -> Path:
    """获取 plugin_sdk 目录"""
    base = get_install_dir()
    if is_frozen():
        return base / "plugin_sdk"
    return base / "src" / "plugin_sdk"


# ═══════════════════════════════════════════════════════════════════
# 动态读取类型
# ═══════════════════════════════════════════════════════════════════

def discover_events() -> list[dict[str, Any]]:
    """发现可用的事件类型"""
    events = []
    events_file = get_shared_types_dir() / "events.py"

    if not events_file.exists():
        return events

    content = events_file.read_text(encoding="utf-8")
    import re
    pattern = r'class\s+(\w+)\s*\(.*?\):'
    for match in re.finditer(pattern, content):
        name = match.group(1)
        if name.endswith("Event"):
            doc_pattern = rf'class\s+{name}\s*\(.*?\):\s*"""(.*?)"""'
            doc_match = re.search(doc_pattern, content, re.DOTALL)
            doc = doc_match.group(1).strip() if doc_match else ""
            events.append({"name": name, "description": doc})

    return events


def discover_commands() -> list[dict[str, Any]]:
    """发现可用的控制命令类型"""
    commands = []
    commands_file = get_shared_types_dir() / "commands.py"

    if not commands_file.exists():
        return commands

    content = commands_file.read_text(encoding="utf-8")
    import re
    pattern = r'class\s+(\w+)\s*\(.*?\):'
    for match in re.finditer(pattern, content):
        name = match.group(1)
        if name.endswith("Command"):
            doc_pattern = rf'class\s+{name}\s*\(.*?\):\s*"""(.*?)"""'
            doc_match = re.search(doc_pattern, content, re.DOTALL)
            doc = doc_match.group(1).strip() if doc_match else ""
            commands.append({"name": name, "description": doc})

    return commands


# ═══════════════════════════════════════════════════════════════════
# 代码生成 - 单文件模式
# ═══════════════════════════════════════════════════════════════════

def _to_class_name(name: str) -> str:
    """将插件名转换为类名前缀

    Examples:
        test_plugin -> TestPlugin
        history -> History
        my_awesome_plugin -> MyAwesomePlugin
    """
    return "".join(word.capitalize() for word in name.split("_"))


def generate_single_file_plugin(
    name: str,
    description: str = "",
    version: str = "1.0.0",
    author: str = "",
    window_mode: str = "TAB",
    icon_color: str = "#4CAF50",
    icon_char: str = "",
    events: list[str] = None,
    commands: list[str] = None,
    needs_config: bool = False,
    needs_service: bool = False,
    service_name: str = "",
) -> str:
    """生成单文件插件代码"""
    if events is None:
        events = []
    if commands is None:
        commands = []

    if not icon_char:
        icon_char = name[0].upper()

    needs_gui = window_mode != "CLOSED"
    class_prefix = _to_class_name(name)
    lines = []

    # 文件头
    lines.append(f'"""')
    lines.append(f'{name} - {description}')
    lines.append(f'"""')
    lines.append('from __future__ import annotations')
    lines.append('')

    # 导入
    imports = []
    if needs_gui:
        imports.append(
            'from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel')
        imports.append('from PyQt5.QtCore import pyqtSignal')

    sdk_imports = ['BasePlugin', 'PluginInfo']
    if needs_gui:
        sdk_imports.extend(['make_plugin_icon', 'WindowMode'])
    if needs_config:
        sdk_imports.extend(['OtherInfoBase', 'BoolConfig'])
    imports.append(f'from plugin_sdk import {", ".join(sdk_imports)}')

    if events:
        imports.append(f'from shared_types.events import {", ".join(events)}')
    if commands:
        imports.append(
            f'from shared_types.commands import {", ".join(commands)}')
    if needs_service and service_name:
        imports.append(f'from plugins.services.{name} import {service_name}')

    lines.extend(imports)
    lines.append('')

    # 配置类
    if needs_config:
        lines.append(f'class {class_prefix}Config(OtherInfoBase):')
        lines.append(f'    """插件配置"""')
        lines.append('    ')
        lines.append('    enable_feature = BoolConfig(')
        lines.append('        default=True,')
        lines.append('        label="启用功能",')
        lines.append('    )')
        lines.append('')
        lines.append('')

    # Widget 类
    widget_name = f'{class_prefix}Widget'
    if needs_gui:
        lines.append(f'class {widget_name}(QWidget):')
        lines.append(f'    """插件 UI"""')
        lines.append('    ')
        lines.append('    _update_signal = pyqtSignal(str)')
        lines.append('')
        lines.append('    def __init__(self, parent=None):')
        lines.append('        super().__init__(parent)')
        lines.append('        layout = QVBoxLayout(self)')
        lines.append('        ')
        lines.append('        self._label = QLabel("就绪")')
        lines.append('        layout.addWidget(self._label)')
        lines.append('        ')
        lines.append('        self._update_signal.connect(self._on_update)')
        lines.append('')
        lines.append('    def _on_update(self, text: str) -> None:')
        lines.append('        """更新显示文本"""')
        lines.append('        self._label.setText(text)')
        lines.append('')
        lines.append('')

    # 主插件类
    plugin_name = f'{class_prefix}Plugin'
    lines.append(f'class {plugin_name}(BasePlugin[{class_prefix}Config]):')
    lines.append(f'    """{description}"""')
    lines.append('')

    # plugin_info
    lines.append('    @classmethod')
    lines.append('    def plugin_info(cls) -> PluginInfo:')
    lines.append('        return PluginInfo(')
    lines.append(f'            name="{name}",')
    lines.append(f'            version="{version}",')
    if author:
        lines.append(f'            author="{author}",')
    lines.append(f'            description="{description}",')

    if needs_gui:
        lines.append(f'            window_mode=WindowMode.{window_mode},')
        lines.append(
            f'            icon=make_plugin_icon("{icon_color}", "{icon_char}"),')
    else:
        lines.append(f'            window_mode=WindowMode.CLOSED,')

    if needs_config:
        lines.append(f'            other_info={class_prefix}Config,')
    if commands:
        lines.append(f'            required_controls=[{", ".join(commands)}],')

    lines.append('        )')
    lines.append('')

    # _setup_subscriptions
    lines.append('    def _setup_subscriptions(self) -> None:')
    if events:
        for event in events:
            handler_name = f'_on_{event.lower().replace("event", "")}'
            lines.append(
                f'        self.subscribe({event}, self.{handler_name})')
    else:
        lines.append('        pass')
    lines.append('')

    # _create_widget
    if needs_gui:
        lines.append('    def _create_widget(self) -> QWidget | None:')
        lines.append(f'        self._widget = {widget_name}()')
        lines.append('        return self._widget')
        lines.append('')

    # on_initialized
    lines.append('    def on_initialized(self) -> None:')
    lines.append(f'        self.logger.info("{plugin_name} 已初始化")')

    if needs_service and service_name:
        lines.append('        ')
        lines.append('        # 注册服务接口')
        lines.append(
            f'        self.register_service(self, protocol={service_name})')
        lines.append(f'        self.logger.info("{service_name} 已注册")')

    if commands:
        lines.append('        ')
        lines.append('        # 检查控制权限')
        for cmd in commands:
            lines.append(f'        has_auth = self.has_control_auth({cmd})')
            lines.append(
                f'        self.logger.info(f"{cmd} 权限: {{has_auth}}")')

    if needs_config:
        lines.append('        ')
        lines.append(
            '        self.config_changed.connect(self._on_config_changed)')

    lines.append('')

    # on_control_auth_changed
    if commands:
        lines.append(
            '    def on_control_auth_changed(self, cmd_type, granted: bool) -> None:')
        lines.append('        """控制权限变更回调"""')
        for cmd in commands:
            lines.append(f'        if cmd_type == {cmd}:')
            lines.append('            self.logger.info(f"权限变更: {granted}")')
        lines.append('')

    # _on_config_changed
    if needs_config:
        lines.append(
            '    def _on_config_changed(self, name: str, value) -> None:')
        lines.append('        """配置变化回调"""')
        lines.append('        self.logger.info(f"配置变化: {name} = {value}")')
        lines.append('')

    # 事件处理器 - 带类型提示
    for event in events:
        handler_name = f'_on_{event.lower().replace("event", "")}'
        lines.append(f'    def {handler_name}(self, event: {event}) -> None:')
        lines.append(f'        """处理 {event}"""')
        lines.append(f'        self.logger.info(f"收到 {event}")')
        if needs_gui:
            lines.append('        # self._widget._update_signal.emit("...")')
        lines.append('')

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════
# 代码生成 - 模块化包结构
# ═══════════════════════════════════════════════════════════════════

def generate_package_files(
    name: str,
    description: str = "",
    version: str = "1.0.0",
    author: str = "",
    window_mode: str = "TAB",
    icon_color: str = "#4CAF50",
    icon_char: str = "",
    events: list[str] = None,
    commands: list[str] = None,
    needs_config: bool = False,
    needs_service: bool = False,
    service_name: str = "",
) -> dict[str, str]:
    """生成模块化包结构的多个文件"""
    if events is None:
        events = []
    if commands is None:
        commands = []

    if not icon_char:
        icon_char = name[0].upper()

    needs_gui = window_mode != "CLOSED"
    class_prefix = _to_class_name(name)
    files = {}

    # ═══════════════════════════════════════════════════════════════════
    # config.py
    # ═══════════════════════════════════════════════════════════════════
    if needs_config:
        config_lines = [
            '"""',
            f'{name} - 配置定义',
            '"""',
            'from __future__ import annotations',
            '',
            'from plugin_sdk import OtherInfoBase, BoolConfig',
            '',
            '',
            f'class {class_prefix}Config(OtherInfoBase):',
            '    """插件配置"""',
            '    ',
            '    enable_feature = BoolConfig(',
            '        default=True,',
            '        label="启用功能",',
            '    )',
        ]
        files['config.py'] = '\n'.join(config_lines)

    # ═══════════════════════════════════════════════════════════════════
    # widgets.py
    # ═══════════════════════════════════════════════════════════════════
    if needs_gui:
        widget_lines = [
            '"""',
            f'{name} - UI 组件',
            '"""',
            'from __future__ import annotations',
            '',
            'from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel',
            'from PyQt5.QtCore import pyqtSignal',
            '',
            '',
            f'class {class_prefix}Widget(QWidget):',
            '    """插件 UI"""',
            '    ',
            '    _update_signal = pyqtSignal(str)',
            '',
            '    def __init__(self, parent=None):',
            '        super().__init__(parent)',
            '        layout = QVBoxLayout(self)',
            '        ',
            '        self._label = QLabel("就绪")',
            '        layout.addWidget(self._label)',
            '        ',
            '        self._update_signal.connect(self._on_update)',
            '',
            '    def _on_update(self, text: str) -> None:',
            '        """更新显示文本"""',
            '        self._label.setText(text)',
        ]
        files['widgets.py'] = '\n'.join(widget_lines)

    # 注意：服务接口不放在插件包内，而是放在 plugins/services/{name}.py
    # 由 cmd_create 函数单独处理

    # ═══════════════════════════════════════════════════════════════════
    # plugin.py
    # ═══════════════════════════════════════════════════════════════════
    plugin_lines = [
        '"""',
        f'{name} - 插件主类',
        '"""',
        'from __future__ import annotations',
        '',
    ]

    # 导入
    if needs_gui:
        plugin_lines.append('from PyQt5.QtWidgets import QWidget')

    sdk_imports = ['BasePlugin', 'PluginInfo']
    if needs_gui:
        sdk_imports.extend(['make_plugin_icon', 'WindowMode'])
    plugin_lines.append(f'from plugin_sdk import {", ".join(sdk_imports)}')

    if events:
        plugin_lines.append(
            f'from shared_types.events import {", ".join(events)}')
    if commands:
        plugin_lines.append(
            f'from shared_types.commands import {", ".join(commands)}')

    if needs_gui:
        plugin_lines.append(f'from .widgets import {class_prefix}Widget')
    if needs_config:
        plugin_lines.append(f'from .config import {class_prefix}Config')
    if needs_service and service_name:
        plugin_lines.append(
            f'from plugins.services.{name} import {service_name}')

    plugin_lines.append('')
    plugin_lines.append('')

    # 主插件类
    plugin_name = f'{class_prefix}Plugin'
    plugin_lines.append(
        f'class {plugin_name}(BasePlugin[{class_prefix}Config]):')
    plugin_lines.append(f'    """{description}"""')
    plugin_lines.append('')

    # plugin_info
    plugin_lines.append('    @classmethod')
    plugin_lines.append('    def plugin_info(cls) -> PluginInfo:')
    plugin_lines.append('        return PluginInfo(')
    plugin_lines.append(f'            name="{name}",')
    plugin_lines.append(f'            version="{version}",')
    if author:
        plugin_lines.append(f'            author="{author}",')
    plugin_lines.append(f'            description="{description}",')

    if needs_gui:
        plugin_lines.append(
            f'            window_mode=WindowMode.{window_mode},')
        plugin_lines.append(
            f'            icon=make_plugin_icon("{icon_color}", "{icon_char}"),')
    else:
        plugin_lines.append(f'            window_mode=WindowMode.CLOSED,')

    if needs_config:
        plugin_lines.append(f'            other_info={class_prefix}Config,')
    if commands:
        plugin_lines.append(
            f'            required_controls=[{", ".join(commands)}],')

    plugin_lines.append('        )')
    plugin_lines.append('')

    # _setup_subscriptions
    plugin_lines.append('    def _setup_subscriptions(self) -> None:')
    if events:
        for event in events:
            handler_name = f'_on_{event.lower().replace("event", "")}'
            plugin_lines.append(
                f'        self.subscribe({event}, self.{handler_name})')
    else:
        plugin_lines.append('        pass')
    plugin_lines.append('')

    # _create_widget
    if needs_gui:
        plugin_lines.append('    def _create_widget(self) -> QWidget | None:')
        plugin_lines.append(f'        self._widget = {class_prefix}Widget()')
        plugin_lines.append('        return self._widget')
        plugin_lines.append('')

    # on_initialized
    plugin_lines.append('    def on_initialized(self) -> None:')
    plugin_lines.append(f'        self.logger.info("{plugin_name} 已初始化")')

    if needs_service and service_name:
        plugin_lines.append('        ')
        plugin_lines.append('        # 注册服务接口')
        plugin_lines.append(
            f'        self.register_service(self, protocol={service_name})')
        plugin_lines.append(f'        self.logger.info("{service_name} 已注册")')

    if commands:
        plugin_lines.append('        ')
        plugin_lines.append('        # 检查控制权限')
        for cmd in commands:
            plugin_lines.append(
                f'        has_auth = self.has_control_auth({cmd})')
            plugin_lines.append(
                f'        self.logger.info(f"{cmd} 权限: {{has_auth}}")')

    if needs_config:
        plugin_lines.append('        ')
        plugin_lines.append(
            '        self.config_changed.connect(self._on_config_changed)')

    plugin_lines.append('')

    # on_control_auth_changed
    if commands:
        plugin_lines.append(
            '    def on_control_auth_changed(self, cmd_type, granted: bool) -> None:')
        plugin_lines.append('        """控制权限变更回调"""')
        for cmd in commands:
            plugin_lines.append(f'        if cmd_type == {cmd}:')
            plugin_lines.append(
                '            self.logger.info(f"权限变更: {granted}")')
        plugin_lines.append('')

    # _on_config_changed
    if needs_config:
        plugin_lines.append(
            '    def _on_config_changed(self, name: str, value) -> None:')
        plugin_lines.append('        """配置变化回调"""')
        plugin_lines.append(
            '        self.logger.info(f"配置变化: {name} = {value}")')
        plugin_lines.append('')

    # 事件处理器 - 带类型提示
    for event in events:
        handler_name = f'_on_{event.lower().replace("event", "")}'
        plugin_lines.append(
            f'    def {handler_name}(self, event: {event}) -> None:')
        plugin_lines.append(f'        """处理 {event}"""')
        plugin_lines.append(f'        self.logger.info(f"收到 {event}")')
        if needs_gui:
            plugin_lines.append(
                '        # self._widget._update_signal.emit("...")')
        plugin_lines.append('')

    files['plugin.py'] = '\n'.join(plugin_lines)

    # ═══════════════════════════════════════════════════════════════════
    # __init__.py
    # ═══════════════════════════════════════════════════════════════════
    init_lines = [
        '"""',
        f'{name} - {description}',
        '"""',
        'from __future__ import annotations',
        '',
        f'from .plugin import {plugin_name}',
        '',
        f'__all__ = ["{plugin_name}"]',
    ]
    files['__init__.py'] = '\n'.join(init_lines)

    return files


def generate_service_interface(service_name: str, description: str = "") -> str:
    """生成服务接口文件"""
    # 从 ServiceName 提取基础名（去掉 Service 后缀）
    base_name = service_name.replace("Service", "")

    lines = [
        '"""',
        f'{service_name} 服务接口',
        '"""',
        'from __future__ import annotations',
        '',
        'from typing import Protocol, runtime_checkable',
        'from dataclasses import dataclass',
        '',
        '',
        '# @dataclass(frozen=True, slots=True)',
        f'# class {base_name}Data:',
        '#     """数据类型"""',
        '#     id: int',
        '#     name: str',
        '',
        '',
        '@runtime_checkable',
        f'class {service_name}(Protocol):',
        '    """服务接口定义"""',
        '    pass',
        '',
        '# 示例方法（取消注释后使用）:',
        f'#     def get_data(self, id: int) -> {base_name}Data | None: ...',
        f'#     def list_data(self, limit: int = 100) -> list[{base_name}Data]: ...',
        '',
    ]
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════
# 命令行接口
# ═══════════════════════════════════════════════════════════════════

def cmd_discover(args):
    """发现可用的类型"""
    result = {
        "environment": "frozen" if is_frozen() else "dev",
        "install_dir": str(get_install_dir()),
        "plugins_dir": str(get_plugins_dir()),
        "shared_types_dir": str(get_shared_types_dir()),
        "events": discover_events(),
        "commands": discover_commands(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_create(args):
    """创建插件"""
    plugins_dir = get_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)

    created_files = []

    # 生成服务接口文件（放在 plugins/services/{name}.py）
    if args.service:
        services_dir = plugins_dir / "services"
        services_dir.mkdir(parents=True, exist_ok=True)

        class_prefix = _to_class_name(args.name)
        service_name = f"{class_prefix}Service"

        service_content = generate_service_interface(
            service_name=service_name,
            description=args.description or "",
        )

        service_file = services_dir / f"{args.name}.py"
        service_file.write_text(service_content, encoding="utf-8")
        created_files.append(str(service_file))

    if args.package:
        # 包形式 - 生成多个文件
        files = generate_package_files(
            name=args.name,
            description=args.description or "",
            version=args.version,
            author=args.author or "",
            window_mode=args.window_mode,
            icon_color=args.icon_color,
            icon_char=args.icon_char or "",
            events=args.events.split(",") if args.events else [],
            commands=args.commands.split(",") if args.commands else [],
            needs_config=args.config,
            needs_service=args.service,
            service_name=_to_class_name(
                args.name) + "Service" if args.service else "",
        )

        pkg_dir = plugins_dir / args.name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in files.items():
            file_path = pkg_dir / filename
            file_path.write_text(content, encoding="utf-8")
            created_files.append(str(file_path))

        result = {
            "success": True,
            "is_package": True,
            "files": created_files,
        }
    else:
        # 单文件形式
        code = generate_single_file_plugin(
            name=args.name,
            description=args.description or "",
            version=args.version,
            author=args.author or "",
            window_mode=args.window_mode,
            icon_color=args.icon_color,
            icon_char=args.icon_char or "",
            events=args.events.split(",") if args.events else [],
            commands=args.commands.split(",") if args.commands else [],
            needs_config=args.config,
            needs_service=args.service,
            service_name=_to_class_name(
                args.name) + "Service" if args.service else "",
        )

        plugin_file = plugins_dir / f"{args.name}.py"
        plugin_file.write_text(code, encoding="utf-8")
        created_files.append(str(plugin_file))

        result = {
            "success": True,
            "is_package": False,
            "files": created_files,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="插件创建工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # discover 命令
    p_discover = subparsers.add_parser("discover", help="发现可用的类型")
    p_discover.set_defaults(func=cmd_discover)

    # create 命令
    p_create = subparsers.add_parser("create", help="创建插件")
    p_create.add_argument("--name", required=True, help="插件名称")
    p_create.add_argument("--description", default="", help="插件描述")
    p_create.add_argument("--version", default="1.0.0", help="版本号")
    p_create.add_argument("--author", default="", help="作者")
    p_create.add_argument("--window-mode", default="TAB",
                          choices=["TAB", "DETACHED", "CLOSED"], help="窗口模式")
    p_create.add_argument("--icon-color", default="#4CAF50", help="图标颜色")
    p_create.add_argument("--icon-char", default="", help="图标字符")
    p_create.add_argument("--package", action="store_true", help="创建包形式插件")
    p_create.add_argument("--events", default="", help="订阅的事件，逗号分隔")
    p_create.add_argument("--commands", default="", help="需要的控制权限，逗号分隔")
    p_create.add_argument("--config", type=lambda x: x.lower() == "true", default=True, help="是否需要配置系统（默认True）")
    p_create.add_argument("--service", action="store_true", help="需要服务接口")
    p_create.add_argument("--service-name", default="", help="服务接口名称")
    p_create.set_defaults(func=cmd_create)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
