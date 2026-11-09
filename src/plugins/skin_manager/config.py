"""
皮肤管理插件 - 配置定义（自动注册皮肤为下拉框选项）。

参考 clipboard_replay/config.py 的做法：模块导入时扫描皮肤目录，
把每个皮肤自动注册成 ChoiceConfig 的一个选项，插件自己不需要写任何
界面代码，设置对话框会依据配置类型自动生成 QComboBox。

想加皮肤：在 skins/ 下新建一个目录、放好图片即可，下次启动自动出现在
下拉框里，无需修改任何 Python 代码。
"""
from __future__ import annotations

import json
from pathlib import Path

from plugin_sdk import OtherInfoBase, BoolConfig, ChoiceConfig, PathConfig

from .skins import list_skins

# 插件自带皮肤库（源码/打包后都随插件目录一起分发）
BUILTIN_SKINS_DIR = Path(__file__).resolve().parent / "skins"

# "默认皮肤" 固定占一个选项
_DEFAULT_CHOICE = ("", "默认皮肤（不替换）")


def discover_choices(skins_dir: Path | str | None = None) -> list[tuple[str, str]]:
    """扫描皮肤目录，返回 ChoiceConfig 选项列表 [(目录名, 显示名), ...]。

    自带皮肤库与用户配置的额外目录合并；同名皮肤以自带库为准。
    """
    choices: dict[str, str] = dict(list_skins(BUILTIN_SKINS_DIR))
    if skins_dir:
        extra = Path(str(skins_dir).strip())
        for name, display in list_skins(extra):
            choices.setdefault(name, display)
    items = [(name, choices[name]) for name in sorted(choices)]
    return [_DEFAULT_CHOICE, *items]


def register_skins(
    config_type: type[OtherInfoBase],
    choices: list[tuple[str, str]],
) -> None:
    """把皮肤选项注册（或刷新）到配置类的 ChoiceConfig 字段上。

    与 clipboard_replay.add_handler_fields 同样的「自动注册」思路：
    直接替换 skin 字段的 choices，同时刷新已实例化配置对象的 _fields，
    保证设置页下次打开时看到最新列表。
    """
    field = ChoiceConfig(
        default="",
        label="当前皮肤",
        choices=choices,
        description="选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原",
    )
    setattr(config_type, "skin", field)


class SkinManagerConfig(OtherInfoBase):
    """插件配置（皮肤下拉框由 discover_choices 自动注册）"""

    auto_apply = BoolConfig(
        default=True,
        label="启动时自动应用",
        description="插件启动并连接主进程后，自动应用上次选择的皮肤",
    )

    skin = ChoiceConfig(
        default="",
        label="当前皮肤",
        choices=[_DEFAULT_CHOICE],  # 由下方 register_skins 覆盖为实际扫描结果
        description="选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原",
    )

    skins_dir = PathConfig(
        default="",
        label="额外皮肤库目录",
        description="留空则使用插件自带 skins/；填写后与自带皮肤合并",
    )


# ── 模块导入时自动注册：扫描自带皮肤目录，生成下拉框选项 ──
register_skins(SkinManagerConfig, discover_choices())
