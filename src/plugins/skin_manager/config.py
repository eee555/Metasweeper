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

from plugin_sdk import (
    OtherInfoBase, BoolConfig, ChoiceConfig, IntConfig,
)

from .skins import list_skins
from .sound import (
    DEFAULT_PACK, DEFAULT_PACK_LABEL, discover_sound_choices,
)
from .zip_import import ZipImportConfig, imported_dir

# 插件自带皮肤库（源码/打包后都随插件目录一起分发）
BUILTIN_SKINS_DIR = Path(__file__).resolve().parent / "skins"

# "默认皮肤" 固定占一个选项
_DEFAULT_CHOICE = ("", "默认皮肤（不替换）")


def discover_choices() -> list[tuple[str, str]]:
    """扫描皮肤目录，返回 ChoiceConfig 选项列表 [(目录名, 显示名), ...]。

    扫描顺序：自带 skins/ → 插件数据目录 skins/（zip 导入落地处）。
    同名以先扫描到的为准。
    """
    choices: dict[str, str] = dict(list_skins(BUILTIN_SKINS_DIR))
    for name, display in list_skins(imported_dir("skins")):
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


def register_sound_choices(
    config_type: type[OtherInfoBase],
    choices: list[tuple[str, str]],
) -> None:
    """把音效包选项注册到独立的 `sound_pack` 字段上。

    与 `register_skins` 完全分离：皮肤与音效各自扫描、各自刷新，
    一方变动不会重置另一方的下拉框。
    """
    field = ChoiceConfig(
        default="",
        label="当前音效包",
        choices=choices,
        description="选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原",
    )
    setattr(config_type, "sound_pack", field)


class SkinManagerConfig(OtherInfoBase):
    """插件配置（皮肤、音效两套下拉框分别自动注册，互不依赖）"""

    auto_apply = BoolConfig(
        default=True,
        label="启动时自动应用",
        description="插件启动并连接主进程后，自动应用上次选择的皮肤与音效设置",
    )

    # ── 皮肤（原有，独立）──
    skin = ChoiceConfig(
        default="",
        label="当前皮肤",
        choices=[_DEFAULT_CHOICE],  # 由下方 register_skins 覆盖为实际扫描结果
        description="选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原",
    )

    skin_zip = ZipImportConfig(
        default="",
        label="导入皮肤包",
        target_subdir="skins",
        button_text="导入皮肤 zip",
        description="选择 zip 自动解压到本插件数据目录 skins/，随后即可在下拉框选择",
    )

    # ── 音效（新增，与皮肤完全独立）──
    sound_enabled = BoolConfig(
        default=False,
        label="启用游戏音效",
        description="通过 SetSoundCommand 独立控制；不影响主程序设置页里的开关",
    )

    sound_volume = IntConfig(
        default=70,
        label="音效音量",
        min_value=0,
        max_value=100,
        use_slider=True,
        description="0~100，选择后立即生效",
    )

    sound_pack = ChoiceConfig(
        default="",
        label="当前音效包",
        choices=[(DEFAULT_PACK, DEFAULT_PACK_LABEL)],
        description="选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原",
    )

    sound_zip = ZipImportConfig(
        default="",
        label="导入音效包",
        target_subdir="sounds",
        button_text="导入音效 zip",
        description="选择 zip 自动解压到本插件数据目录 sounds/，随后即可在下拉框选择",
    )


# ── 模块导入时自动注册：两套目录各自扫描，互不影响 ──
register_skins(SkinManagerConfig, discover_choices())
register_sound_choices(SkinManagerConfig, discover_sound_choices())


def refresh_all_choices():
    """zip 导入后重新扫描两套目录并刷新已注册的下拉框选项。"""
    register_skins(SkinManagerConfig, discover_choices())
    register_sound_choices(SkinManagerConfig, discover_sound_choices())
