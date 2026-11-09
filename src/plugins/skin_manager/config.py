"""
皮肤管理插件 - 配置定义（自动注册皮肤为下拉框选项）。

参考 clipboard_replay/config.py 的做法：模块导入时扫描皮肤目录，
把每个皮肤自动注册成 ChoiceConfig 的一个选项，插件自己不需要写任何
界面代码，设置对话框会依据配置类型自动生成 QComboBox。

想加皮肤：在 skins/ 下新建一个目录、放好图片即可，下次启动自动出现在
下拉框里，无需修改任何 Python 代码。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from plugin_sdk import (
    OtherInfoBase, BoolConfig, ChoiceConfig, IntConfig,
)
from shared_types.sounds import default_pack_label, default_skin_label

from .skins import list_skins
from .sound import discover_sound_choices
from .zip_import import ZipImportConfig, imported_dir

_translate = QCoreApplication.translate

# 插件自带皮肤库（源码/打包后都随插件目录一起分发）
BUILTIN_SKINS_DIR = Path(__file__).resolve().parent / "skins"

# "默认皮肤" 固定占一个选项（运行时按当前语言取词）
_DEFAULT_CHOICE = ("", default_skin_label())


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


def register_choices(
    config_type: type[OtherInfoBase],
    field_name: str,
    choices: list[tuple[str, str]],
) -> None:
    """把选项注册（或刷新）到配置类的 ChoiceConfig 字段上。

    皮肤与音效共用同一套注册逻辑，只差字段名与文案；此前两个近乎相同的
    函数各写一份，新增字段时容易漏改。
    """
    is_skin = field_name == "skin"
    field = ChoiceConfig(
        default="",
        label=_translate("SkinManager", "当前皮肤" if is_skin else "当前音效包"),
        choices=choices,
        description=_translate(
            "SkinManager",
            "选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原"
            if is_skin else
            "选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原",
        ),
    )
    setattr(config_type, field_name, field)


def _i18n_config_strings() -> None:
    """lupdate 扫描用哑函数：注册函数里的文案以条件表达式传入 translate，
    静态扫描器可能无法抽取，这里逐条硬编码补齐。"""
    _translate("SkinManager", "当前皮肤")
    _translate("SkinManager", "当前音效包")
    _translate("SkinManager",
               "选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原")
    _translate("SkinManager",
               "选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原")


class SkinManagerConfig(OtherInfoBase):
    """插件配置（皮肤、音效两套下拉框分别自动注册，互不依赖）"""

    auto_apply = BoolConfig(
        default=True,
        label=_translate("SkinManager", "启动时自动应用"),
        description=_translate(
            "SkinManager", "插件启动并连接主进程后，自动应用上次选择的皮肤与音效设置"),
    )

    # ── 皮肤 ──
    skin = ChoiceConfig(
        default="",
        label=_translate("SkinManager", "当前皮肤"),
        choices=[_DEFAULT_CHOICE],  # 由下方 register_choices 覆盖为实际扫描结果
        description=_translate(
            "SkinManager",
            "选择后立即生效（纯内存热替换，不重启）；选「默认皮肤」即还原"),
    )

    skin_zip = ZipImportConfig(
        default="",
        label=_translate("SkinManager", "导入皮肤包"),
        target_subdir="skins",
        button_text=_translate("SkinManager", "导入皮肤 zip"),
        description=_translate(
            "SkinManager",
            "选择 zip 自动解压到本插件数据目录 skins/，随后即可在下拉框选择"),
    )

    # ── 音效 ──
    sound_enabled = BoolConfig(
        default=False,
        label=_translate("SkinManager", "启用游戏音效"),
        description=_translate(
            "SkinManager",
            "通过 SetSoundCommand 独立控制；不影响主程序设置页里的开关"),
    )

    sound_volume = IntConfig(
        default=70,
        label=_translate("SkinManager", "音效音量"),
        min_value=0,
        max_value=100,
        use_slider=True,
        description=_translate("SkinManager", "0~100，选择后立即生效"),
    )

    sound_pack = ChoiceConfig(
        default="",
        label=_translate("SkinManager", "当前音效包"),
        choices=[("", default_pack_label())],
        description=_translate(
            "SkinManager",
            "选择后立即生效（纯内存热替换，不重启）；选「默认音效」即还原"),
    )

    sound_zip = ZipImportConfig(
        default="",
        label=_translate("SkinManager", "导入音效包"),
        target_subdir="sounds",
        button_text=_translate("SkinManager", "导入音效 zip"),
        description=_translate(
            "SkinManager",
            "选择 zip 自动解压到本插件数据目录 sounds/，随后即可在下拉框选择"),
    )


# ── 模块导入时自动注册：两套目录各自扫描，互不影响 ──
register_choices(SkinManagerConfig, "skin", discover_choices())
register_choices(SkinManagerConfig, "sound_pack", discover_sound_choices())
