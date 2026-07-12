from PyQt5 import QtCore
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QApplication
import superGUI
from config.constants import (
    READY, PLAYING, JOKING, SHOW, STUDY, SHOW_DISPLAY,
    FACE_SMILE, FACE_CLICK, BOARD_READY, BOARD_WIN, BOARD_LOSS,
    CELL_UNOPENED, CELL_FLAGGED,
)
from shared_types.events import ButtonClickEvent
from shared_types.enums import ButtonEventType, MouseState
from plugin_sdk.server_bridge import GameServerBridge
from utils.app_logger import logger

# 局面中的鼠标和滚轮事件

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
            logger.warning("Failed to send button event to plugins", exc_info=True)

    def _step_and_send(self, mouse_event: str, i: int, j: int):
        old = MouseState(self.label.ms_board.mouse_state)
        self.label.ms_board.step(mouse_event, (i, j))
        self._send_button_event(ButtonEventType.from_display_name(mouse_event), i, j, old,
                                MouseState(self.label.ms_board.mouse_state))

    def mineAreaLeftPressed(self, i, j):
        # print("lc", i, j)
        try:
            if self.game_state == READY or self.game_state == PLAYING or\
                    self.game_state == JOKING:
                self._step_and_send('lc', i, j)
                self.label.update()
                self.set_face(FACE_CLICK)

            elif self.game_state == SHOW:
                # 看概率时，所有操作都移出局面外
                self._step_and_send('lc', self.row * self.pixSize, self.column * self.pixSize)
                self.set_face(FACE_CLICK)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def mineAreaLeftRelease(self, i, j):
        # print("lr", i, j)
        try:
            if self.game_state == READY:
                if not self.pos_is_in_board(i, j):
                    self._step_and_send('lr', i, j)
                else:
                    used_pending = False
                    if self.label.ms_board.mouse_state == MouseState.DownUp.value and\
                            self.label.ms_board.game_board[i // self.pixSize][j // self.pixSize] == CELL_UNOPENED:
                        # 正式埋雷开始
                        used_pending = self.layMine(i // self.pixSize, j // self.pixSize)

                        if any((used_pending, self.board_constraint, self._allowed_controls)):
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

                    # 回放局面时，第一次点击的位置可能原本就是雷，需要 ai 介入重新排雷
                    if used_pending:
                        self.ai(i // self.pixSize, j // self.pixSize)

                    self._step_and_send('lr', i, j)

                    if self.label.ms_board.game_board_state == BOARD_WIN:
                        # 点一下可能获胜
                        self.gameWin()
                        self.label.update()
                        return
                    elif self.label.ms_board.game_board_state == BOARD_LOSS:
                        # 点一下可能踩雷（F3重开）
                        self.gameFailed()
                        self.label.update()
                        return
                    else:
                        self.label.update()
                        self._send_board_update_event()
                self.set_face(FACE_SMILE)
            elif self.game_state == PLAYING or self.game_state == JOKING:
                # 如果是游戏中，且是左键抬起（不是双击），且是在10上，且在局面内，则用ai劫持、处理下
                if self.pos_is_in_board(i, j):
                    if self.label.ms_board.game_board[i // self.pixSize][j // self.pixSize] == CELL_UNOPENED \
                            and self.label.ms_board.mouse_state == MouseState.DownUp.value:
                        self.ai(i // self.pixSize, j // self.pixSize)
                    self.chording_ai(i // self.pixSize, j // self.pixSize)
                self._step_and_send('lr', i, j)

                if self.label.ms_board.game_board_state == BOARD_WIN:
                    self.gameWin()
                    self.label.update()
                    return
                elif self.label.ms_board.game_board_state == BOARD_LOSS:
                    self.gameFailed()
                    self.label.update()
                    return
                self.label.update()
                self._send_board_update_event()
                self.set_face(FACE_SMILE)

            elif self.game_state == SHOW:
                # 看概率时，所有操作都移出局面外
                self._step_and_send('lr', self.row * self.pixSize, self.column * self.pixSize)
                self.set_face(FACE_SMILE)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def mineAreaRightPressed(self, i, j):
        # print("rc", i, j)
        try:
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
                self._step_and_send('rc', i, j)
                self.label.update()
                self.set_face(FACE_CLICK)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def mineAreaRightRelease(self, i, j):
        # print("rr", i, j)
        try:
            if self.game_state == READY or self.game_state == PLAYING or self.game_state == JOKING:
                self.chording_ai(i // self.pixSize, j // self.pixSize)
                self._step_and_send('rr', i, j)
                self.label.update()
                self._send_board_update_event()
                self.set_face(FACE_SMILE)
            elif self.game_state == SHOW:
                # 看概率时，所有操作都移出局面外
                self._step_and_send('rr', self.row * self.pixSize, self.column * self.pixSize)
                self.set_face(FACE_SMILE)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def mineAreaLeftAndRightPressed(self, i, j):
        # print("cc", i, j)
        try:
            if self.game_state == READY or self.game_state == PLAYING or\
                    self.game_state == JOKING:
                self._step_and_send('cc', i, j)
                self.label.update()
                self.set_face(FACE_CLICK)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def mineMouseMove(self, i, j):
        # 正常情况的鼠标移动事件，与高亮的显示有关
        try:
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def resizeWheel(self, i, x, y):
        # 按住ctrl滚轮，调整局面大小
        # study状态下，滚轮修改局面
        # 函数名要改了
        if QApplication.keyboardModifiers() == Qt.ControlModifier and\
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
