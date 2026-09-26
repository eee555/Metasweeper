"""
修仙升级数据模型
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
_translate = QCoreApplication.translate


class _I18nDict:
    """每次访问都动态翻译的类 dict 对象"""

    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        src = self._data.get(key)
        if src is None:
            return default
        return _translate("Form", src)

    def __getitem__(self, key):
        return _translate("Form", self._data[key])


# ═══════════════════════════════════════════════════════════════
# 仙逆修仙等级名称表（0-100级）
# ═══════════════════════════════════════════════════════════════
_LEVEL_NAMES_SRC: dict[int, str] = {
    0: "凡人",
    1: "凝气一层",
    2: "凝气二层",
    3: "凝气三层",
    4: "凝气四层",
    5: "凝气五层",
    6: "凝气六层",
    7: "凝气七层",
    8: "凝气八层",
    9: "凝气九层",
    10: "凝气十层",
    11: "凝气十一层",
    12: "凝气十二层",
    13: "凝气十三层",
    14: "凝气十四层",
    15: "凝气十五层",
    16: "筑基初期",
    17: "筑基中期",
    18: "筑基后期",
    19: "筑基大圆满",
    20: "结丹初期",
    21: "结丹中期",
    22: "结丹后期",
    23: "结丹大圆满",
    24: "元婴初期",
    25: "元婴中期",
    26: "元婴后期",
    27: "元婴大圆满",
    28: "化神初期",
    29: "化神中期",
    30: "化神后期",
    31: "化神大圆满",
    32: "婴变初期",
    33: "婴变中期",
    34: "婴变后期",
    35: "婴变大圆满",
    36: "问鼎初期",
    37: "问鼎中期",
    38: "问鼎后期",
    39: "问鼎大圆满",
    40: "阴虚",
    41: "阳实",
    42: "窥涅初期",
    43: "窥涅中期",
    44: "窥涅后期",
    45: "窥涅大圆满",
    46: "净涅初期",
    47: "净涅中期",
    48: "净涅后期",
    49: "净涅大圆满",
    50: "碎涅初期",
    51: "碎涅中期",
    52: "碎涅后期",
    53: "碎涅大圆满",
    54: "天人一衰",
    55: "天人二衰",
    56: "天人三衰",
    57: "天人四衰",
    58: "天人五衰",
    59: "空涅初期",
    60: "空涅中期",
    61: "空涅后期",
    62: "空涅大圆满",
    63: "空灵初期",
    64: "空灵中期",
    65: "空灵后期",
    66: "空灵大圆满",
    67: "空玄初期",
    68: "空玄中期",
    69: "空玄后期",
    70: "空玄大圆满",
    71: "空玄一劫",
    72: "空玄二劫",
    73: "空玄三劫",
    74: "空玄四劫",
    75: "空玄五劫",
    76: "空玄六劫",
    77: "空玄七劫",
    78: "空玄八劫",
    79: "空玄九劫",
    80: "空劫初期",
    81: "空劫中期",
    82: "空劫后期",
    83: "空劫大圆满",
    84: "大尊",
    85: "金尊",
    86: "天尊",
    87: "跃天尊",
    88: "大天尊",
    89: "踏天一桥",
    90: "踏天二桥",
    91: "踏天三桥",
    92: "踏天四桥",
    93: "踏天五桥",
    94: "踏天六桥",
    95: "踏天七桥",
    96: "踏天八桥",
    97: "踏天九桥",
    98: "踏天境",
    99: "厚土境",
    100: "煌天境",
}

LEVEL_NAMES: _I18nDict = _I18nDict(_LEVEL_NAMES_SRC)


# 游戏难度映射
_LEVEL_LABELS_SRC: dict[int, str] = {
    3: "初级",
    4: "中级",
    5: "高级",
    6: "自定义",
}

LEVEL_LABELS: _I18nDict = _I18nDict(_LEVEL_LABELS_SRC)


# 游戏模式映射
_MODE_LABELS_SRC: dict[int, str] = {
    0: "标准",
    4: "Win7",
    5: "经典无猜",
    6: "强无猜",
    7: "弱无猜",
    8: "准无猜",
    9: "强可猜",
    10: "弱可猜",
}

MODE_LABELS: _I18nDict = _I18nDict(_MODE_LABELS_SRC)


# 仙躯形象：仅大境界突破换图，量变不换（共18张：1.png~18.png）
# 每个 tuple 为 (该大境界起始等级, 图片索引)
REALM_IMAGE: list[tuple[int, int]] = [
    (0,  1),   # 凡人
    (1,  1),   # 凝气
    (16, 2),   # 筑基
    (20, 3),   # 结丹
    (24, 4),   # 元婴
    (28, 5),   # 化神
    (32, 6),   # 婴变
    (36, 7),   # 问鼎
    (40, 8),   # 阴虚阳实
    (42, 9),   # 窥涅
    (46, 10),  # 净涅
    (50, 11),  # 碎涅
    (54, 12),  # 天人五衰
    (59, 13),  # 空涅
    (63, 14),  # 空灵
    (67, 15),  # 空玄（含空玄九劫）
    (80, 16),  # 空劫
    (84, 17),  # 大尊~大天尊
    (89, 18),  # 踏天~煌天境
]


def get_image_index(level: int) -> int:
    for start, idx in reversed(REALM_IMAGE):
        if level >= start:
            return idx
    return 1


def _i18n_hints():
    """pylupdate5 扫描哑函数：提取动态翻译的字符串"""
    _translate("Form", "凡人")
    _translate("Form", "凝气一层")
    _translate("Form", "凝气二层")
    _translate("Form", "凝气三层")
    _translate("Form", "凝气四层")
    _translate("Form", "凝气五层")
    _translate("Form", "凝气六层")
    _translate("Form", "凝气七层")
    _translate("Form", "凝气八层")
    _translate("Form", "凝气九层")
    _translate("Form", "凝气十层")
    _translate("Form", "凝气十一层")
    _translate("Form", "凝气十二层")
    _translate("Form", "凝气十三层")
    _translate("Form", "凝气十四层")
    _translate("Form", "凝气十五层")
    _translate("Form", "筑基初期")
    _translate("Form", "筑基中期")
    _translate("Form", "筑基后期")
    _translate("Form", "筑基大圆满")
    _translate("Form", "结丹初期")
    _translate("Form", "结丹中期")
    _translate("Form", "结丹后期")
    _translate("Form", "结丹大圆满")
    _translate("Form", "元婴初期")
    _translate("Form", "元婴中期")
    _translate("Form", "元婴后期")
    _translate("Form", "元婴大圆满")
    _translate("Form", "化神初期")
    _translate("Form", "化神中期")
    _translate("Form", "化神后期")
    _translate("Form", "化神大圆满")
    _translate("Form", "婴变初期")
    _translate("Form", "婴变中期")
    _translate("Form", "婴变后期")
    _translate("Form", "婴变大圆满")
    _translate("Form", "问鼎初期")
    _translate("Form", "问鼎中期")
    _translate("Form", "问鼎后期")
    _translate("Form", "问鼎大圆满")
    _translate("Form", "阴虚")
    _translate("Form", "阳实")
    _translate("Form", "窥涅初期")
    _translate("Form", "窥涅中期")
    _translate("Form", "窥涅后期")
    _translate("Form", "窥涅大圆满")
    _translate("Form", "净涅初期")
    _translate("Form", "净涅中期")
    _translate("Form", "净涅后期")
    _translate("Form", "净涅大圆满")
    _translate("Form", "碎涅初期")
    _translate("Form", "碎涅中期")
    _translate("Form", "碎涅后期")
    _translate("Form", "碎涅大圆满")
    _translate("Form", "天人一衰")
    _translate("Form", "天人二衰")
    _translate("Form", "天人三衰")
    _translate("Form", "天人四衰")
    _translate("Form", "天人五衰")
    _translate("Form", "空涅初期")
    _translate("Form", "空涅中期")
    _translate("Form", "空涅后期")
    _translate("Form", "空涅大圆满")
    _translate("Form", "空灵初期")
    _translate("Form", "空灵中期")
    _translate("Form", "空灵后期")
    _translate("Form", "空灵大圆满")
    _translate("Form", "空玄初期")
    _translate("Form", "空玄中期")
    _translate("Form", "空玄后期")
    _translate("Form", "空玄大圆满")
    _translate("Form", "空玄一劫")
    _translate("Form", "空玄二劫")
    _translate("Form", "空玄三劫")
    _translate("Form", "空玄四劫")
    _translate("Form", "空玄五劫")
    _translate("Form", "空玄六劫")
    _translate("Form", "空玄七劫")
    _translate("Form", "空玄八劫")
    _translate("Form", "空玄九劫")
    _translate("Form", "空劫初期")
    _translate("Form", "空劫中期")
    _translate("Form", "空劫后期")
    _translate("Form", "空劫大圆满")
    _translate("Form", "大尊")
    _translate("Form", "金尊")
    _translate("Form", "天尊")
    _translate("Form", "跃天尊")
    _translate("Form", "大天尊")
    _translate("Form", "踏天一桥")
    _translate("Form", "踏天二桥")
    _translate("Form", "踏天三桥")
    _translate("Form", "踏天四桥")
    _translate("Form", "踏天五桥")
    _translate("Form", "踏天六桥")
    _translate("Form", "踏天七桥")
    _translate("Form", "踏天八桥")
    _translate("Form", "踏天九桥")
    _translate("Form", "踏天境")
    _translate("Form", "厚土境")
    _translate("Form", "煌天境")
    _translate("Form", "初级")
    _translate("Form", "中级")
    _translate("Form", "高级")
    _translate("Form", "自定义")
    _translate("Form", "标准")
    _translate("Form", "Win7")
    _translate("Form", "经典无猜")
    _translate("Form", "强无猜")
    _translate("Form", "弱无猜")
    _translate("Form", "准无猜")
    _translate("Form", "强可猜")
    _translate("Form", "弱可猜")
