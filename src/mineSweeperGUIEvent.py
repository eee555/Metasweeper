from typing import NamedTuple

from PySide6 import QtCore
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QApplication
import superGUI
from config.constants import (
    READY, PLAYING, JOKING, WIN, FAIL, JOWIN, JOFAIL, SHOW, STUDY, SHOW_DISPLAY,
    FACE_SMILE, FACE_CLICK, BOARD_READY, BOARD_WIN, BOARD_LOSS,
    CELL_UNOPENED, CELL_FLAGGED,
)
from shared_types.events import ButtonClickEvent
from shared_types.enums import ButtonEventType, MouseState
from plugin_sdk.server_bridge import GameServerBridge
from utils.app_logger import logger
from utils.sound_manager import SoundManager
from shared_types.sounds import SoundEvent, SOUND_PRIORITY

# 局面中的鼠标和滚轮事件

# 问号格子编码（与 skin_manager.skins.CELL_FILES 里的 17 一致）；
# config.constants 未登记，因为本项目默认禁用问号。
_CELL_QUESTION = 17


class BoardSnapshot(NamedTuple):
    """一次 step 前后的棋盘计数快照，用于统一判定开格/插旗/拔旗/问号。"""
    opened: int
    flags: int
    questions: int


class MineSweeperGUIEvent(superGUI.Ui_MainWindow):
    def _send_button_event(self, button: ButtonEventType, i: int, j: int,
                           old_state: MouseState, new_state: MouseState):
        try:
            event = ButtonClickEvent(
                col=j // self.pixSize,
                row=i // self.pixSize,
                button=button,
                old_state=old_state,
                new_state=new_state,
            )
            GameServerBridge.instance().send_event(event)
        except Exception:
            logger.warning(
                "Failed to send button event to plugins", exc_info=True)

    def _step_and_send(self, mouse_event: str, i: int, j: int) -> MouseState:
        old = MouseState(self.label.ms_board.mouse_state)
        logger.debug(f"step {mouse_event} @({i},{j}) mouse_state={old.name}")
        self.label.ms_board.step(mouse_event, (i, j))
        self._send_button_event(ButtonEventType.from_display_name(mouse_event), i, j, old,
                                MouseState(self.label.ms_board.mouse_state))
        # 返回 step 前的鼠标状态，供反馈层识别双击（chording）
        return old

    def _snapshot(self) -> BoardSnapshot:
        # 一次遍历同时统计开格(0~8)、旗(11)、问号(17)数量，
        # 供 step 前后做差，避免多次全盘扫描。
        opened = flags = questions = 0
        for row in self.label.ms_board.game_board:
            for v in row:
                if 0 <= v <= 8:
                    opened += 1
                elif v == CELL_FLAGGED:
                    flags += 1
                elif v == _CELL_QUESTION:
                    questions += 1
        return BoardSnapshot(opened, flags, questions)

    def _finish(self, win: bool) -> None:
        """真实鼠标操作导致结局时统一走这里：先播结局音，再改状态。

        刻意不把播放放进 gameWin()/gameFailed()，因为后者可能被录像回放、
        自动重开等路径复用；这 6 个调用点都位于真实鼠标操作分支。
        WIN/LOSE 属于独占事件，会自动 stop_all() 清掉同帧的 START/OPEN，
        因此第一击直接踩雷也不会叠音。
        """
        SoundManager.instance().play(
            SoundEvent.WIN if win else SoundEvent.LOSE)
        if win:
            self.gameWin()
        else:
            self.gameFailed()

    def _emit_feedback(self, before: BoardSnapshot, *,
                       old_state: MouseState | None = None,
                       is_start: bool = False,
                       action: str = "lr") -> None:
        """一次 step 后的统一反馈出口：棋盘抖动 + 游戏音效。

        由一次全盘 diff 同时判定开格/双击/插旗/拔旗，并按优先级合并成
        单个 cue（intensity 取最大值），避免一次操作响多声。
        点已开格、无效点击、看概率(SHOW)、录像回放均不会走到这里。

        `action` 为本次鼠标事件名：CHORD 只在真正的左键抬起（lr）且 step 前
        鼠标状态为 chording 类时成立。标雷递归模式下 rc/rr 也会级联开格，
        此时一律按 OPEN 处理，避免误响 CHORD。
        """
        after = self._snapshot()
        d_open = after.opened - before.opened
        d_flag = after.flags - before.flags

        # 开格打击感：开格数增加才触发弱档抖动（含第一击），保持原有手感
        if d_open > 0:
            self.label.start_shake()

        sm = SoundManager.instance()
        if is_start:
            # 第一击只响开局音，压掉该次 OPEN/CHORD，避免两段音叠一起发糊
            sm.play(SoundEvent.START)
            return

        cues: list[tuple[int, SoundEvent, int]] = []
        if d_open > 0:
            chord = action == "lr" and old_state in (
                MouseState.Chording, MouseState.ChordingNotFlag,
                MouseState.DownUpAfterChording,
            )
            event = SoundEvent.CHORD if chord else SoundEvent.OPEN
            cues.append((SOUND_PRIORITY[event], event, d_open))

        # 三个变化各自独立收集，再由优先级排序取最高；此前用 if/elif
        # 让「旗 + 问号同时变化」在 d_flag>0 与 d_flag<0 时得到两种相反
        # 处理（一边吞问号、一边吞拔旗），属于逻辑不一致。
        if d_flag > 0:
            # 标雷递归模式下一次 rc 可能级联标多面旗，intensity 体现数量
            cues.append(
                (SOUND_PRIORITY[SoundEvent.FLAG_ON], SoundEvent.FLAG_ON, d_flag))
        elif d_flag < 0:
            cues.append(
                (SOUND_PRIORITY[SoundEvent.FLAG_OFF], SoundEvent.FLAG_OFF, -d_flag))

        if not cues:
            return
        # 同一操作只播优先级最高的一个；强度取所有 cue 的最大值，
        # 合并只丢数量，不丢「这一下有多大」。
        cues.sort(key=lambda c: c[0], reverse=True)
        intensity = max(c[2] for c in cues)
        sm.play(cues[0][1], intensity=intensity)

    def mineAreaLeftPressed(self, i, j):
        # print("lc", i, j)
        if self.game_state == READY or self.game_state == PLAYING or\
                self.game_state == JOKING:
            self._step_and_send('lc', i, j)
            self.label.update()
            self.set_face(FACE_CLICK)

        elif self.game_state == SHOW:
            # 看概率时，所有操作都移出局面外
            self._step_and_send('lc', self.row * self.pixSize,
                                self.column * self.pixSize)
            self.set_face(FACE_CLICK)

    def mineAreaLeftRelease(self, i, j):
        # print("lr", i, j)
        if self.game_state == READY:
            started_now = False
            if not self.pos_is_in_board(i, j):
                self._step_and_send('lr', i, j)
            else:
                if self.label.ms_board.mouse_state == MouseState.DownUp.value and\
                        self.label.ms_board.game_board[i // self.pixSize][j // self.pixSize] == CELL_UNOPENED:
                    # 正式埋雷开始
                    self.layMine(i // self.pixSize, j // self.pixSize)
                    started_now = True

                    if any((self.board_constraint, self._allowed_controls)):
                        self.game_state = JOKING
                    else:
                        self.game_state = PLAYING

                    # 假如未开启"直播模式"，禁用代码截图
                    if self.player_identifier[:6] != "[live]":
                        self.disable_screenshot()
                    else:
                        self.enable_screenshot()

                    if self.cursor_limit:
                        self.limit_cursor()

                    # 核实用的时间，防变速齿轮
                    self.start_time_unix_2 = QtCore.QDateTime.currentDateTime().\
                        toMSecsSinceEpoch()
                    self.timer_10ms.start()
                    # 禁用双击修改指标名称公式
                    self.score_board_manager.editing_row = -2

                # F3等upk局面时，第一次点击的位置可能原本就是雷，需要 ai 介入重新排雷
                if self.engine.use_pending_boards_flag:
                    self.ai(i // self.pixSize, j // self.pixSize)

                before = self._snapshot()
                old = self._step_and_send('lr', i, j)
                self._emit_feedback(before, old_state=old, is_start=started_now)

                if self.label.ms_board.game_board_state == BOARD_WIN:
                    # 点一下可能获胜
                    self._finish(win=True)
                    self.label.update()
                    return
                elif self.label.ms_board.game_board_state == BOARD_LOSS:
                    # 点一下可能踩雷（F3重开）
                    self._finish(win=False)
                    self.label.update()
                    return
                else:
                    self.label.update()
                    self._send_board_update_event()
            self.set_face(FACE_SMILE)
        elif self.game_state == PLAYING or self.game_state == JOKING:
            # 游戏进行中的左键/双击：无猜、可猜等模式的重排与判负由局面状态机自行处理
            before = self._snapshot()
            old = self._step_and_send('lr', i, j)
            self._emit_feedback(before, old_state=old)

            if self.label.ms_board.game_board_state == BOARD_WIN:
                self._finish(win=True)
                self.label.update()
                return
            elif self.label.ms_board.game_board_state == BOARD_LOSS:
                self._finish(win=False)
                self.label.update()
                return
            self.label.update()
            self._send_board_update_event()
            self.set_face(FACE_SMILE)

        elif self.game_state == SHOW:
            # 看概率时，所有操作都移出局面外
            self._step_and_send('lr', self.row * self.pixSize,
                                self.column * self.pixSize)
            self.set_face(FACE_SMILE)

    def mineAreaLeftDoubleRelease(self, i, j):
        if self.double_click_restart and self.game_state in (WIN, FAIL, JOWIN, JOFAIL) \
                and self.pos_is_in_board(i, j):
            # 在第二次抬起时重开，避免此次抬起继续操作新棋盘。
            self.gameRestart()
        else:
            self.mineAreaLeftRelease(i, j)

    def mineAreaRightPressed(self, i, j):
        # print("rc", i, j)
        if self.game_state == READY or self.game_state == PLAYING or self.game_state == JOKING:
            if i < self.pixSize * self.row and j < self.pixSize * self.column:
                # 计算左上角显示的雷数用。必须校验：当前格的状态、鼠标状态为双键都抬起。
                # 假如按下左键，再切屏（比如快捷键截图），再左键抬起，再切回来，再右键按下，
                # 就会导致DownUp状态下右键按下。此时不应该标雷，左上角雷数也应该不变
                if self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == CELL_FLAGGED and\
                        self.label.ms_board.mouse_state == MouseState.UpUp.value:
                    self.mineUnFlagedNum += 1
                    self.showMineNum(self.mineUnFlagedNum)
                elif self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == CELL_UNOPENED and\
                        self.label.ms_board.mouse_state == MouseState.UpUp.value:
                    self.mineUnFlagedNum -= 1
                    self.showMineNum(self.mineUnFlagedNum)
            # 标旗实际发生在 rc（右键按下），故此处必须做 diff；
            # 递归模式下一次 rc 可能级联标多面旗，用全盘快照才能覆盖。
            before = self._snapshot()
            old = self._step_and_send('rc', i, j)
            self._emit_feedback(before, old_state=old, action="rc")
            # 标雷递归模式（12/13/15/16）下，一次标雷可能经级联直接获胜或踩雷，
            # 必须像 lr 一样检查结局，否则计时器继续走，会被防变速齿轮守卫误判重开
            if self.label.ms_board.game_board_state == BOARD_WIN:
                self._finish(win=True)
                self.label.update()
                return
            elif self.label.ms_board.game_board_state == BOARD_LOSS:
                self._finish(win=False)
                self.label.update()
                return
            self.label.update()
            self.set_face(FACE_CLICK)

    def mineAreaRightRelease(self, i, j):
        # print("rr", i, j)
        if self.game_state == READY or self.game_state == PLAYING or self.game_state == JOKING:
            before = self._snapshot()
            old = self._step_and_send('rr', i, j)
            self._emit_feedback(before, old_state=old, action="rr")
            self.label.update()
            self._send_board_update_event()
            self.set_face(FACE_SMILE)
        elif self.game_state == SHOW:
            # 看概率时，所有操作都移出局面外
            self._step_and_send('rr', self.row * self.pixSize,
                                self.column * self.pixSize)
            self.set_face(FACE_SMILE)

    def mineAreaLeftAndRightPressed(self, i, j):
        # 2026-11-09 与上游作者确认：不再记录 'cc' 事件，双键按下按 Qt 报告的
        # 实际按键（e.button()）忠实转发为 lc/rc，双击由状态机在解析时合成。
        # 此槽保留仅为兼容旧信号连接，正常路径不会再被触发。
        logger.debug(f"leftAndRightPressed legacy path hit @({i},{j}), ignored")

    def mineMouseMove(self, i, j):
        # 正常情况的鼠标移动事件，与高亮的显示有关
        if self.game_state == PLAYING or self.game_state == JOKING or self.game_state == READY:
            # self._step_and_send('mv', i, j)
            self.label.ms_board.step('mv', (i, j))
            self.label.update()
        # 按住空格后的鼠标移动事件，与概率的显示有关
        elif self.game_state == SHOW or self.game_state == STUDY:
            if not self.pos_is_in_board(i, j):
                self.label_info.setText(_translate("Form", '(是雷的概率)'))
            else:
                text4 = '{:.3f}'.format(
                    max(0, self.label.boardProbability[i//self.pixSize][j//self.pixSize]))
                self.label_info.setText(text4)
        # 播放录像时的鼠标移动事件
        elif self.game_state == SHOW_DISPLAY:
            if not self.pos_is_in_board(i, j):
                self.label_info.setText(_translate("Form", '(是雷的概率)'))
            else:
                text4 = '{:.3f}'.format(
                    max(0, self.label.ms_board.game_board_poss[i//self.pixSize][j//self.pixSize]))
                self.label_info.setText(text4)

    def resizeWheel(self, i, x, y):
        # 按住ctrl滚轮，调整局面大小
        # study状态下，滚轮修改局面
        # 函数名要改了
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier and\
                self.game_state == READY and self.label.ms_board.game_board_state == BOARD_READY:
            # 调整局面大小需要满足：ui端是ready且状态机是ready
            if i > 0:
                self.pixSize += 1
            elif i < 0:
                self.pixSize -= 1

        elif self.game_state == STUDY:
            if x < 0 or x >= self.row or y < 0 or y >= self.column:
                return
            v = self.label.ms_board.game_board[x][y]
            if i > 0:
                v += 1
                if v == 9:
                    v = 10
                elif v >= 10:
                    v = 0
            elif i < 0:
                v -= 1
                if v == 9:
                    v = 8
                elif v <= -1:
                    v = 10
            self.label.ms_board.game_board[x][y] = v
            self.render_poss_on_board()
