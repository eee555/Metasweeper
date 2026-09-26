"""
共享枚举类型

定义游戏状态、鼠标状态、游戏模式、游戏难度等枚举。
这些枚举遵循 evf 标准（ms_toollib 也遵循此标准）。

参考：https://github.com/eee555/ms-toollib/blob/main/evf%E6%A0%87%E5%87%86.md
"""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QCoreApplication

_translate = QCoreApplication.translate


class BaseDiaPlayEnum(Enum):
    """带显示名称的枚举基类"""

    @property
    def display_name(self) -> str:
        return self.name

    @classmethod
    def from_display_name(cls, display_name: str) -> "BaseDiaPlayEnum":
        for member in cls:
            if member.display_name == display_name:
                return member
        raise ValueError(f"Invalid display name: {display_name}")

    @classmethod
    def display_names(cls) -> list[str]:
        return [member.display_name for member in cls]

    @classmethod
    def try_create(cls, value: int) -> "BaseDiaPlayEnum | int":
        """尝试创建枚举，如果值不在定义中则返回原始值"""
        try:
            return cls(value)
        except ValueError:
            return value


class GameBoardState(BaseDiaPlayEnum):
    """
    游戏板状态枚举

    这些魔数遵循Metasweeper的状态标准，不遵循ms_toollib标准。
    'ready'、'study'、'show'、'playing'、'joking'、
    # 'fail'、'win'、'jofail'、'jowin'、'display'、'showdisplay'
    jofail：作弊过且失败
    jowin：作弊过且成功
    display：播放录像中
    showdisplay：播放录像的同时显示是雷的概率
    study：研究模式（摆雷模式）
    show：游戏过程中正在按下空格显示是雷的概率
    joking：作弊后游戏中
    playing：游戏中
    """
    Ready = 0
    Study = 1
    Show = 2
    Playing = 3
    Joking = 4
    Fail = 5
    Win = 6
    Jofail = 7
    Jowin = 8
    Display = 9
    ShowDisplay = 10

    @property
    def display_name(self) -> str:
        match self:
            case GameBoardState.Ready:
                return _translate("Form", "准备")
            case GameBoardState.Study:
                return _translate("Form", "研究模式")
            case GameBoardState.Show:
                return _translate("Form", "显示概率")
            case GameBoardState.Playing:
                return _translate("Form", "游戏中")
            case GameBoardState.Joking:
                return _translate("Form", "作弊中")
            case GameBoardState.Fail:
                return _translate("Form", "失败")
            case GameBoardState.Win:
                return _translate("Form", "胜利")
            case GameBoardState.Jofail:
                return _translate("Form", "作弊且失败")
            case GameBoardState.Jowin:
                return _translate("Form", "作弊且成功")
            case GameBoardState.Display:
                return _translate("Form", "播放录像中")
            case GameBoardState.ShowDisplay:
                return _translate("Form", "播放录像时显示概率")
            case _:
                return str(self.value)


class MouseState(BaseDiaPlayEnum):
    """
    鼠标状态枚举

    游戏过程中，鼠标的动作会触发鼠标事件，并在 evf 录像中记录为
    诸如 "mv", "lc", "lr", "rc", "rr", "mc", "mr", "pf", "cc", "l", "r", "m"
    动作导致鼠标转移至不同的状态，用于计算左键、右键、双击等次数，显示局面高亮等。

    这些魔数遵循 ms_toollib 标准。
    """
    UpUp = 1
    UpDown = 2
    UpDownNotFlag = 3
    DownUp = 4
    Chording = 5
    ChordingNotFlag = 6
    DownUpAfterChording = 7
    Undefined = 8

    @property
    def display_name(self) -> str:
        match self:
            case MouseState.UpUp:
                return _translate("Form", "双键抬起")
            case MouseState.UpDown:
                return _translate("Form", "右键按下且标过雷")
            case MouseState.UpDownNotFlag:
                return _translate("Form", "右键按下且没有标过雷")
            case MouseState.DownUp:
                return _translate("Form", "左键按下")
            case MouseState.Chording:
                return _translate("Form", "双键按下")
            case MouseState.ChordingNotFlag:
                return _translate("Form", "双键按下且先按下右键且没有标雷")
            case MouseState.DownUpAfterChording:
                return _translate("Form", "双击后先弹起右键左键还没有弹起")
            case MouseState.Undefined:
                return _translate("Form", "未初始化")
            case _:
                return str(self.value)


class GameMode(BaseDiaPlayEnum):
    """
    游戏模式枚举

    这些魔数遵循 evf 标准（ms_toollib 也是遵循 evf 标准）。
    """
    Standard = 0
    UPK = 1
    Win7 = 4
    ClassicNoGuess = 5
    StrictNoGuess = 6
    WeakNoGuess = 7
    BlessingMode = 8
    GuessableNoGuess = 9
    LuckyMode = 10

    @property
    def display_name(self) -> str:
        match self:
            case GameMode.Standard:
                return _translate("Form", "标准")
            case GameMode.UPK:
                return _translate("Form", "UPK")
            case GameMode.Win7:
                return _translate("Form", "win7")
            case GameMode.ClassicNoGuess:
                return _translate("Form", "经典无猜")
            case GameMode.StrictNoGuess:
                return _translate("Form", "强无猜")
            case GameMode.WeakNoGuess:
                return _translate("Form", "弱无猜")
            case GameMode.BlessingMode:
                return _translate("Form", "准无猜")
            case GameMode.GuessableNoGuess:
                return _translate("Form", "强可猜")
            case GameMode.LuckyMode:
                return _translate("Form", "弱可猜")
            case _:
                return str(self.value)


class GameLevel(BaseDiaPlayEnum):
    """
    游戏难度枚举

    这些魔数遵循 evf 标准（ms_toollib 也是遵循 evf 标准）。
    """
    BEGINNER = 3
    INTERMEDIATE = 4
    EXPERT = 5
    CUSTOM = 6

    @property
    def display_name(self) -> str:
        match self:
            case GameLevel.BEGINNER:
                return _translate("Form", "初级")
            case GameLevel.INTERMEDIATE:
                return _translate("Form", "中级")
            case GameLevel.EXPERT:
                return _translate("Form", "高级")
            case GameLevel.CUSTOM:
                return _translate("Form", "自定义")
            case _:
                return str(self.value)


class ButtonEventType(BaseDiaPlayEnum):
    """
    鼠标按键事件类型枚举

    遵循 evf 标准，这些值对应录像文件中记录的事件类型：
      mv=1、lc=2、lr=3、rc=4、rr=5、mc=6、mr=7、pf=8、cc=9、l=10、r=11、m=12
    """
    # mv：鼠标移动
    MV = 1
    # lc：左键按下
    LC = 2
    # lr：左键释放
    LR = 3
    # rc：右键按下
    RC = 4
    # rr：右键抬起
    RR = 5
    # mc（不推荐）：中键按下（相当于双键按下）
    MC = 6
    # mr（不推荐）：中键抬起（相当于双键抬起）
    MR = 7
    # pf（不推荐）：在游戏开始前的标雷。一些复刻版本不记录游戏开始前
    # （即第一次有效的左键抬起前）的过程（例如游戏开始前的标雷、左键按下及之后的移动），
    # 而是直接记录标了哪些雷。这个操作不能用"rc"+"rr"来等价，因为涉及到右键次数如何计算的问题。
    # 举例来说，开始前，先标一个雷，再在另一个位置上反复标雷、取消标雷，再左键开始游戏，
    # 此时整局游戏的右键数如何计算？ms_toollib 中，pf 标记记录 right+1、flag+1，
    # 但这不一定准确。
    PF = 8
    # cc（不推荐）：文件中记录双键按下，但不知道哪个按键按下，需要结合解析器中的
    # 鼠标状态自动机，看当时哪个按键是抬起的。
    CC = 9
    # l（不推荐）：左键的按下或抬起，需要结合解析器中的鼠标状态自动机，看到底是按下还是抬起。
    L = 10
    # r（不推荐）：右键的按下或抬起，需要结合解析器中的鼠标状态自动机，看到底是按下还是抬起。
    R = 11
    # m（不推荐）：中键的按下或抬起，需要结合解析器中的鼠标状态自动机，看到底是按下还是抬起。
    M = 12

    @property
    def display_name(self) -> str:
        return self.name.lower()
