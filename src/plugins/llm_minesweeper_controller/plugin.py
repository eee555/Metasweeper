"""
llm_minesweeper_controller - 插件主类
"""
from __future__ import annotations

from ctypes import cast
import hashlib
import json
from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QThread, pyqtSignal

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from plugin_sdk.config_types import OtherInfoBase
from shared_types.events import BoardUpdateEvent, GameStatusChangeEvent
from shared_types.commands import NewGameCommand, MouseClickCommand

from .widgets import LlmMinesweeperControllerWidget
from .config import LlmMinesweeperControllerConfig
from .api_client import LLMClient, ChatResponse
from .function_registry import FunctionRegistry


# 系统提示词（写死在代码中）
SYSTEM_PROMPT = """你是一个扫雷AI。你只能通过调用工具来操作游戏。

# 棋盘格式（最重要！）
- 棋盘是 `cells[row][col]` 二维数组
- `row` 是行索引（0开始，从上到下）
- `col` 是列索引（0开始，从左到右）
- **只能左键点击 `cells[row][col] == -1` 的未揭开格子！**
- 已揭开的格子（值为 0-8）不能再次点击！
- 值为 `F` 的已标旗格子也不能点击！

# 游戏阶段判断（根据 game_status 字段！）

## 阶段1：开局（game_status=ready）
- 棋盘全部是 `-1`（未揭开）
- **必须直接执行第一次点击！** 不要反复查询！
- 选择中间区域的格子，如 `click_cell(row=rows//2, col=cols//2, button="left")`

## 阶段2：正常游戏（game_status=playing）
按照下方决策树操作。

## 阶段3：游戏结束
- game_status=win → 调用 start_new_game 开始新游戏
- game_status=fail → 调用 start_new_game 开始新游戏

# 决策树（阶段2时使用，按此顺序检查！）

## 检查1：能标旗吗？→ 右键 `"right"`
```
对于每个数字N：
  周围 `-1` 格子数 = N ？
  → 是：这N个格子必定是雷 → `click_cell(row=X, col=Y, button="right")` 标旗
```
**标旗点击的是 `-1` 未揭开格子！右键只会标旗，不会揭开格子！**
- 右键点击 `-1` 格子 = 标旗（F）
- 右键点击已标旗（F）格子 = 取消标旗

## 检查2：能中键吗？→ 中键 `"middle"`
```
对于每个数字N：
  周围已标旗数 = N ？
  → 是：周围剩余 `-1` 格子全部安全 → `click_cell(row=X, col=Y, button="middle")` 批量揭开
```
**中键点击的是数字格子（N），不是 `-1` 格子！**

## 检查3：能左键吗？→ 左键 `"left"`
```
不属于以上两种情况，但确定安全？
→ 是：`click_cell(row=X, col=Y, button="left")` 揭开周围的 `-1` 格子
```
**左键点击的是 `-1` 未揭开格子！左键只能点击 `-1` 格子来揭开！**

## 强制规则
- 点击 `-1` 格子：只能左键（揭开）或右键（标旗）
- 点击数字格子：只能中键（批量揭开周围）
- 检查顺序：标旗 → 中键 → 左键，**不能跳过**

# 棋盘与状态定义
- 格子状态：`-1`(未揭开)、`0-8`(周围雷数)、`F`(已标旗)、`M`(踩到的红雷)、`m`(未踩的白雷)
- game_status: `ready`(准备), `playing`(游戏中), `win`(胜利), `fail`(失败)

# 可用工具
- `get_board_state()`：获取全局视图，返回 `cells[row][col]` 格式。
- `click_cell(row, col, button)`：执行操作，**row和col必须是未被揭开的 `-1` 格子**。
  - button `"left"` 揭开格子
  - button `"right"` 标旗/取消标旗
  - button `"middle"` 快速揭开周围格子
- `start_new_game(difficulty)`：开始新游戏，`difficulty`为 `"easy"`、`"medium"` 或 `"hard"`。
"""


class ExecutionSummary:
    """执行摘要，用于压缩历史上下文"""

    def __init__(self):
        self.actions: List[Dict[str, Any]] = []  # 记录执行的操作详情
        self.queries: int = 0
        self.clicks: int = 0
        self.flags: int = 0
        self.unflags: int = 0
        self.middles: int = 0
        self.games_started: int = 0
        self.last_game_status: str = ""

    def add_action(self, func_name: str, args: Dict, result: str):
        """添加一个操作记录"""
        action = {"func": func_name, "args": args,
                  "result_preview": self._shorten_result(result)}
        self.actions.append(action)

        if func_name == "get_board_state":
            self.queries += 1
        elif func_name == "click_cell":
            button = args.get("button", "")
            if button == "left":
                self.clicks += 1
            elif button == "right":
                # 检查是否取消标旗
                result_lower = result.lower()
                if "取消" in result or "unflag" in result_lower:
                    self.unflags += 1
                else:
                    self.flags += 1
            elif button == "middle":
                self.middles += 1
        elif func_name == "start_new_game":
            self.games_started += 1
            self.last_game_status = args.get("difficulty", "")

    @staticmethod
    def _shorten_result(result: str, max_len: int = 50) -> str:
        """缩短结果文本"""
        if not result:
            return ""
        result = result.strip()
        if len(result) <= max_len:
            return result
        return result[:max_len] + "..."

    def to_summary_text(self) -> str:
        """生成压缩摘要文本"""
        lines = ["[历史执行摘要]"]

        # 统计信息
        stats = []
        if self.clicks > 0:
            stats.append(f"左键{self.clicks}次")
        if self.flags > 0:
            stats.append(f"标旗{self.flags}次")
        if self.unflags > 0:
            stats.append(f"取消标旗{self.unflags}次")
        if self.middles > 0:
            stats.append(f"中键{self.middles}次")
        if self.queries > 0:
            stats.append(f"查询{self.queries}次")
        if self.games_started > 0:
            stats.append(f"新游戏{self.games_started}次")

        if stats:
            lines.append(f"执行统计: {', '.join(stats)}")

        # 最近的操作记录（简化为统计格式）
        click_actions = [a for a in self.actions if a.get(
            "func") == "click_cell"]
        if click_actions:
            recent = click_actions[-5:]  # 只保留最近5个
            lines.append(f"最近操作({len(click_actions)}个点击):")
            for a in recent:
                args = a["args"]
                button = args.get("button", "")
                col, row = args.get("col"), args.get("row")
                btn_name = {"left": "左", "right": "右",
                            "middle": "中"}.get(button, button)
                lines.append(f"  - {btn_name}键({col},{row})")

        if self.last_game_status:
            lines.append(f"最后游戏: {self.last_game_status}")

        return "\n".join(lines)


class LLMWorker(QThread):
    """LLM 工作线程"""

    log_signal = pyqtSignal(str)
    chat_signal = pyqtSignal(str, str)  # role, text
    finished_signal = pyqtSignal(bool, str)  # success, message
    summary_signal = pyqtSignal(str)  # 上下文摘要更新

    def __init__(self, client: LLMClient, registry: FunctionRegistry,
                 messages: List[Dict[str, Any]], max_history: int = 20,
                 min_history: int = 5,
                 config: Optional["LlmMinesweeperControllerConfig"] = None):
        super().__init__()
        self.client = client
        self.registry = registry
        self.messages = messages
        self.max_history = max_history  # 上限：超过此值触发压缩
        self.min_history = min_history  # 下限：压缩后保留的最少消息数
        self.config = config
        self._stop_flag = False
        self._execution_summary: ExecutionSummary | None = None  # 压缩摘要

    def stop(self) -> None:
        """请求停止工作线程"""
        self._stop_flag = True
        self.requestInterruption()

    def _emit_summary_update(self) -> None:
        """发送摘要更新信号到 UI"""
        if self._execution_summary:
            summary_text = self._execution_summary.to_summary_text()
            self.summary_signal.emit(summary_text)
        else:
            self.summary_signal.emit("")

    def _trim_history(self) -> None:
        """压缩历史消息，只保留下限数量的最近消息"""
        if self.max_history <= 0:
            return

        # 移除旧的压缩摘要
        self.messages[:] = [m for m in self.messages
                            if not (m.get("role") == "user" and "[上下文压缩]" in (m.get("content") or ""))]

        # 分离消息
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        other_msgs = [m for m in self.messages if m.get("role") != "system"]

        # 如果超过上限，压缩旧消息到下限
        if len(other_msgs) > self.max_history:
            old_msgs = other_msgs[:-self.min_history]  # 保留下限数量的消息
            self._compress_history(old_msgs)

        # 移除旧的压缩摘要（压缩后又插入了）
        self.messages[:] = [m for m in self.messages
                            if not (m.get("role") == "user" and "[上下文压缩]" in (m.get("content") or ""))]

        # 重新分离并截取到下限
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        other_msgs = [m for m in self.messages if m.get("role") != "system"]

        if len(other_msgs) > self.min_history:
            other_msgs = other_msgs[-self.min_history:]

        # 构建最终消息列表
        result = system_msgs[:]

        # 插入压缩摘要（如果有）
        if self._execution_summary and (self._execution_summary.actions or
                                        self._execution_summary.queries > 0 or self._execution_summary.clicks > 0):
            summary_text = self._execution_summary.to_summary_text()
            result.append({
                "role": "user",
                "content": f"[上下文压缩] 以下是之前的执行摘要:\n{summary_text}"
            })

        # 添加最近的消息（最多到下限）
        result.extend(other_msgs)
        self.messages[:] = result

        # 发送摘要更新信号到 UI
        self._emit_summary_update()

    def _clean_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """清理消息列表，移除无效值，确保API兼容"""
        clean = []
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if not role:
                continue

            clean_msg: Dict[str, Any] = {"role": role}

            # 处理 content - 只能是字符串或None，不能是其他类型
            content = msg.get("content")
            if content is not None and isinstance(content, str):
                clean_msg["content"] = content

            # 处理 tool_calls - 确保格式正确
            tool_calls = msg.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                clean_tcs = []
                for j, tc in enumerate(tool_calls):
                    if not tc:
                        continue
                    func = tc.get("function") or {}
                    args = func.get("arguments", "{}")
                    # arguments 必须是字符串
                    if not isinstance(args, str):
                        args = json.dumps(args, ensure_ascii=False)

                    clean_tc: Dict[str, Any] = {
                        "id": str(tc.get("id") or f"call_{i}_{j}"),
                        "type": "function",
                        "function": {
                            "name": str(func.get("name") or ""),
                            "arguments": args
                        }
                    }
                    clean_tcs.append(clean_tc)

                if clean_tcs:
                    clean_msg["tool_calls"] = clean_tcs

            # 处理 tool 角色的 tool_call_id
            if role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id:
                    clean_msg["tool_call_id"] = str(tool_call_id)
                # tool 消息必须有 content
                tool_content = msg.get("content")
                if tool_content is not None:
                    clean_msg["content"] = str(tool_content)

            clean.append(clean_msg)
        return clean

    def _compress_history(self, old_msgs: List[Dict[str, Any]]) -> None:
        """压缩历史消息：将旧的消息压缩成摘要"""
        # old_msgs 是即将被压缩的旧消息

        if not old_msgs:
            return

        # 统计旧消息中的操作 - 按顺序配对 assistant tool_calls 和 tool 结果
        summary = self._execution_summary or ExecutionSummary()

        # 按顺序遍历消息，模拟函数调用流程
        pending_actions: List[Dict] = []  # 待匹配结果的操作

        for msg in old_msgs:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    func_data = tc.get("function", {})
                    func_name = func_data.get("name", "")
                    try:
                        args_str = func_data.get("arguments", "{}")
                        args = json.loads(args_str) if isinstance(
                            args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}
                    pending_actions.append(
                        {"func": func_name, "args": args, "result": ""})

            elif msg.get("role") == "tool":
                # 匹配到 pending_actions 中的操作
                content = msg.get("content", "") or ""
                if pending_actions:
                    action = pending_actions.pop(0)
                    summary.add_action(action["func"], action["args"], content)

        # 如果还有未匹配的操作（异常情况），也加入摘要
        for action in pending_actions:
            summary.add_action(
                action["func"], action["args"], action["result"])

        # 构建压缩摘要消息
        if summary.actions or summary.queries > 0 or summary.clicks > 0:
            self._execution_summary = summary
            summary_text = summary.to_summary_text()
            self.log_signal.emit(f"📦 上下文压缩: 合并了 {len(old_msgs)} 条旧消息")

            # 移除之前的压缩摘要消息（避免累积）
            self.messages[:] = [m for m in self.messages
                                if not (m.get("role") == "user" and "[上下文压缩]" in (m.get("content") or ""))]

            # 在消息列表开头添加压缩摘要（作为 user 消息）
            insert_idx = len(
                [m for m in self.messages if m.get("role") == "system"])
            self.messages.insert(insert_idx, {
                "role": "user",
                "content": f"[上下文压缩] 以下是之前的执行摘要:\n{summary_text}"
            })

    def run(self):
        """执行多轮对话循环（有历史消息上限）"""
        try:
            tools = self.registry.get_tools_schema()
            round_num = 0

            # 连续查询棋盘次数（不含click操作时）
            consecutive_query_count = 0
            MAX_CONSECUTIVE_QUERIES = 3  # 连续3次查询后强制决策

            # 记录最近点击的棋盘状态，用于检测重复点击
            last_click_board_hash = ""
            consecutive_no_change_count = 0
            MAX_CONSECUTIVE_NO_CHANGE = 3  # 连续3次点击后棋盘无变化则警告

            while True:
                # 检查停止标志
                if self._stop_flag or self.isInterruptionRequested():
                    self.finished_signal.emit(False, "用户请求停止")
                    return

                # 只在超过上限时才裁剪历史消息
                current_msg_count = len(
                    [m for m in self.messages if m.get("role") != "system"])
                if current_msg_count > self.max_history:
                    self._trim_history()
                    self.log_signal.emit(
                        f"📦 上下文压缩: {current_msg_count} -> {len([m for m in self.messages if m.get('role') != 'system'])} 条 (上限: {self.max_history}, 下限: {self.min_history})")

                self.log_signal.emit(
                    f"当前历史消息数: {current_msg_count} (上限: {self.max_history}, 下限: {self.min_history})")

                round_num += 1
                self.log_signal.emit(f"=== 第 {round_num} 轮对话 ===")

                # 如果连续查询次数过多，添加强制决策提示
                if consecutive_query_count >= MAX_CONSECUTIVE_QUERIES:
                    force_decision_prompt = (
                        f"[系统] 你已连续查询棋盘 {consecutive_query_count} 次但未执行任何操作！"
                        "现在必须基于已有信息做出决策：要么执行 click_cell 操作，要么调用 start_new_game。"
                        "不要继续查询棋盘状态！"
                    )
                    self.messages.append(
                        {"role": "user", "content": force_decision_prompt})
                    self.log_signal.emit("⚠️ 强制决策：连续查询次数过多，要求AI必须执行操作")
                    consecutive_query_count = 0  # 重置计数

                # 如果连续点击但棋盘无变化，添加强制决策提示
                if consecutive_no_change_count >= MAX_CONSECUTIVE_NO_CHANGE:
                    force_decision_prompt = (
                        f"[系统] 警告！你已连续 {consecutive_no_change_count} 次执行点击操作，但棋盘状态没有变化！"
                        "可能的原因：1) 点击了已揭开的格子 2) 点击了边界外 3) 游戏已结束。"
                        "请先调用 get_board_state 检查当前状态，再决定下一步操作。"
                        "如果游戏已结束（win/fail），必须调用 start_new_game 开始新游戏！"
                    )
                    self.messages.append(
                        {"role": "user", "content": force_decision_prompt})
                    self.log_signal.emit(
                        f"⚠️ 强制检查：连续{consecutive_no_change_count}次点击无效果，要求检查棋盘状态")
                    consecutive_no_change_count = 0  # 重置计数

                # 调用 LLM（清理消息中的无效值）
                clean_messages = self._clean_messages(self.messages)

                # reasoning_effort 参数
                reasoning_effort = None
                if self.config.deep_thinking != "off":
                    reasoning_effort = self.config.deep_thinking

                response: ChatResponse = self.client.chat(
                    messages=clean_messages,
                    tools=tools,
                    temperature=0.2,
                    reasoning_effort=reasoning_effort,
                )

                if not response.success:
                    self.finished_signal.emit(
                        False, f"API 调用失败: {response.error}")
                    return

                # 检查是否需要调用工具
                if response.has_tool_calls:
                    # 构建 assistant 消息，合并 content 和 tool_calls
                    assistant_msg: Dict[str, Any] = {
                        "role": "assistant",
                        "tool_calls": response.tool_calls
                    }
                    if response.has_content:
                        content = response.content or ""
                        self.chat_signal.emit("assistant", content)
                        assistant_msg["content"] = content

                    self.messages.append(assistant_msg)

                    # 处理每个 tool_call
                    has_action = False  # 本轮是否有实际操作
                    for tool_call in response.tool_calls:
                        tool_call_id = tool_call.get("id", "")
                        func_data = tool_call.get("function", {})
                        func_name = func_data.get("name", "")

                        try:
                            func_args_str = func_data.get("arguments", "{}")
                            func_args = json.loads(func_args_str) if isinstance(
                                func_args_str, str) else func_args_str
                        except json.JSONDecodeError:
                            func_args = {}

                        self.log_signal.emit(f"调用函数: {func_name}({func_args})")
                        self.chat_signal.emit(
                            "tool", f"{func_name}({func_args})")

                        # 执行函数
                        result = self.registry.execute_function(
                            func_name, func_args)

                        self.log_signal.emit(f"执行结果: {result}")

                        # 构建 tool 结果消息
                        tool_msg = LLMClient.build_tool_result_message(
                            tool_call_id, result)
                        self.messages.append(tool_msg)

                        # 记录到执行摘要（用于上下文压缩）
                        if self._execution_summary is None:
                            self._execution_summary = ExecutionSummary()
                        self._execution_summary.add_action(
                            func_name, func_args, tool_msg.get("content", ""))
                        # 实时更新摘要显示
                        self._emit_summary_update()

                        # 记录是否有实际操作（click_cell 或 start_new_game）
                        if func_name in ("click_cell", "start_new_game"):
                            has_action = True

                            # 检查棋盘是否真的发生了变化
                            if func_name == "click_cell":
                                current_board = self.registry.execute_function(
                                    "get_board_state", {})
                                if current_board and "cells" in current_board:
                                    board_str = json.dumps(
                                        current_board["cells"], ensure_ascii=False)
                                    current_hash = hashlib.md5(
                                        board_str.encode()).hexdigest()

                                    if current_hash == last_click_board_hash:
                                        consecutive_no_change_count += 1
                                        self.log_signal.emit(
                                            f"⚠️ 棋盘无变化! 连续无变化次数: {consecutive_no_change_count}/{MAX_CONSECUTIVE_NO_CHANGE}")
                                    else:
                                        consecutive_no_change_count = 0
                                        last_click_board_hash = current_hash
                                        self.log_signal.emit("✓ 棋盘已更新")

                    # 根据是否有实际操作更新连续查询计数
                    if has_action:
                        consecutive_query_count = 0
                        self.log_signal.emit("✓ 检测到实际操作，重置查询计数")
                    else:
                        consecutive_query_count += 1
                        self.log_signal.emit(
                            f"⚠️ 无实际操作，连续查询计数: {consecutive_query_count}/{MAX_CONSECUTIVE_QUERIES}")

                    # 继续下一轮对话（让 LLM 处理工具结果）
                    continue

                # 没有 tool_calls，对话结束
                self.finished_signal.emit(True, "LLM 分析完成")
                return

        except Exception as e:
            self.finished_signal.emit(False, f"执行异常: {str(e)}")


class LlmMinesweeperControllerPlugin(BasePlugin[LlmMinesweeperControllerConfig]):
    """使用 LLM 控制扫雷的插件"""

    _widget: LlmMinesweeperControllerWidget

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="llm_minesweeper_controller",
            version="1.0.0",
            description="使用 LLM 分析并控制扫雷游戏",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#4CAF50", "L"),
            other_info=LlmMinesweeperControllerConfig,
            required_controls=[NewGameCommand, MouseClickCommand],
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(BoardUpdateEvent, self._on_board_update)
        self.subscribe(GameStatusChangeEvent, self._on_game_status_change)

    def _create_widget(self) -> QWidget | None:
        self._widget = LlmMinesweeperControllerWidget()
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("LlmMinesweeperControllerPlugin 已初始化")

        # 检查控制权限状态
        self._log_control_auth_status()

        # 初始化组件
        self._init_llm_client()
        self._init_function_registry()

        # 设置 UI 回调
        self._widget.set_test_button_callback(self._test_connection)
        self._widget.set_analyze_callback(self._start_analysis)
        self._widget.set_stop_button_callback(self._stop_analysis)

        # 监听配置变化
        self.config_changed.connect(self._on_config_changed)

        # 当前棋盘状态
        self._current_board: Optional[Dict[str, Any]] = None

        # 当前游戏状态 (1=ready, 2=playing, 3=win, 4=fail, ...)
        self._game_status: int = 1

        # 当前工作线程
        self._worker: Optional[LLMWorker] = None

        # 用户主动停止标志
        self._user_stopped: bool = False

    def _log_control_auth_status(self) -> None:
        """检查控制权限"""
        has_new_game = self.has_control_auth(NewGameCommand)
        has_click = self.has_control_auth(MouseClickCommand)
        self.logger.info(f"NewGameCommand 权限: {has_new_game}")
        self.logger.info(f"MouseClickCommand 权限: {has_click}")
        self._widget.log_message(
            f"权限: NewGame={has_new_game}, MouseClick={has_click}")

    def _init_llm_client(self) -> None:
        """初始化 LLM 客户端"""
        if self.other_info is None:
            return
        api_key = self.other_info.api_key
        base_url = self.other_info.api_base_url
        model = self.other_info.model_name
        timeout = self.other_info.request_timeout

        if api_key:
            self.llm_client = LLMClient(
                api_key=api_key,
                base_url=base_url,
                model=model,
                timeout=timeout,
            )
            self.logger.info("LLM 客户端已初始化")
            self._widget.log_message(f"LLM 客户端已初始化 (model: {model})")
        else:
            self.llm_client = None
            self.logger.warning("未配置 API 密钥")
            self._widget.log_message("未配置 API 密钥，LLM 功能不可用")

    def _init_function_registry(self) -> None:
        """初始化 Function 注册表"""
        self.function_registry = FunctionRegistry()
        self._register_minesweeper_functions()

    def _register_minesweeper_functions(self) -> None:
        """注册扫雷相关的函数"""
        registry = self.function_registry

        @registry.register(
            description="点击指定位置的格子",
            param_descriptions={
                "col": "列索引 (从 0 开始，即 X 坐标)",
                "row": "行索引 (从 0 开始，即 Y 坐标)",
                "button": "鼠标按钮: 'left' 左键揭开, 'right' 右键标旗, 'middle' 中键快速揭开周围格子",
            }
        )
        def click_cell(col: int, row: int, button: str = "left") -> Dict[str, Any]:
            return self._execute_click_cell(col, row, button)

        @registry.register(
            description="开始新游戏，不传难度参数则使用默认难度",
            param_descriptions={
                "difficulty": "游戏难度（可选）: 'easy' 初级(8x8), 'medium' 中级(16x16), 'hard' 高级(16x30)",
            }
        )
        def start_new_game(difficulty: str = None) -> Dict[str, Any]:
            return self._execute_start_new_game(difficulty)

        @registry.register(
            description="获取当前棋盘状态",
        )
        def get_board_state() -> Dict[str, Any]:
            return self._get_current_board_state()

        # @registry.register(
        #     description="获取局部棋盘区域，返回以(col,row)为中心的局部格子，radius自己决定（建议3-5）",
        #     param_descriptions={
        #         "col": "中心列索引 (从 0 开始)",
        #         "row": "中心行索引 (从 0 开始)",
        #         "radius": "半径，自己决定大小，默认3，返回(2*radius+1)x(2*radius+1)的区域",
        #     }
        # )
        # def get_local_board(col: int, row: int, radius: int = 3) -> Dict[str, Any]:
        #     return self._get_local_board(col, row, radius)

    def on_control_auth_changed(self, cmd_type, granted: bool) -> None:
        """控制权限变更回调"""
        if cmd_type == NewGameCommand:
            self._widget.log_message(
                f"NewGameCommand 权限: {'已授权' if granted else '未授权'}")
        elif cmd_type == MouseClickCommand:
            self._widget.log_message(
                f"MouseClickCommand 权限: {'已授权' if granted else '未授权'}")

    def _on_config_changed(self, name: str, value) -> None:
        """配置变化回调"""
        self.logger.info(f"配置变化: {name} = {value}")
        self._widget.log_message(f"配置更新: {name}")

        # API 相关配置变化时重新初始化客户端
        if name in ["api_key", "api_base_url", "model_name", "request_timeout"]:
            self._init_llm_client()

    def _on_board_update(self, event: BoardUpdateEvent) -> None:
        """处理棋盘更新事件"""
        self._widget.log_message("收到棋盘更新事件")

        # 更新当前棋盘状态
        self._current_board = self._extract_board_data(event)

    def _on_game_status_change(self, event: GameStatusChangeEvent) -> None:
        """处理游戏状态变化事件

        状态值：
        - 1: ready (准备)
        - 2: playing (游戏中)
        - 3: win (胜利)
        - 4: fail (失败)
        - 5: show (显示概率)
        - 6: study (研究模式)
        - 7/8: display 相关
        """
        status_names = {
            1: "准备",
            2: "游戏中",
            3: "胜利",
            4: "失败",
            5: "显示概率",
            6: "研究模式",
            7: "播放录像",
            8: "播放概率",
        }

        last_name = status_names.get(
            event.last_status, f"未知({event.last_status})")
        current_name = status_names.get(
            event.current_status, f"未知({event.current_status})")

        self._widget.log_message(f"游戏状态变化: {last_name} -> {current_name}")

        # 始终更新游戏状态
        self._game_status = event.current_status

        # 游戏结束时（win/fail -> ready/playing），清空 worker 的历史上下文
        if event.last_status in (3, 4) and event.current_status in (1, 2):
            if self._worker:
                # 保留系统消息，只清空其他消息
                self._worker.messages[:] = [
                    m for m in self._worker.messages if m.get("role") == "system"]
                # 重置执行摘要
                self._worker._execution_summary = None
                # 通知 UI 摘要已清空
                self._widget.update_summary("")
                self._widget.log_message("已清空历史上下文")

        # 更新状态显示
        if event.current_status == 3:
            self._widget.update_status("游戏胜利!")
        elif event.current_status == 4:
            self._widget.update_status("游戏失败!")
        elif event.current_status == 2:
            self._widget.update_status("游戏中...")

    # ═══════════════════════════════════════════════════════════════
    # LLM 对话流程
    # ═══════════════════════════════════════════════════════════════

    def _test_connection(self) -> None:
        """测试 API 连接"""
        if not self.llm_client:
            self._widget.log_message("请先配置 API 密钥")
            return

        self._widget.log_message("正在测试连接...")
        self._widget.set_buttons_enabled(False)

        response = self.llm_client.test_connection()

        if response.success:
            self._widget.update_status("连接成功")
            self._widget.log_message(f"连接成功! 模型: {self.other_info.model_name}")
        else:
            self._widget.update_status("连接失败")
            self._widget.log_message(f"连接失败: {response.error}")

        self._widget.set_buttons_enabled(True)

    def _auto_continue_analysis(self) -> None:
        """自动继续分析（异常中断后）"""
        if self._game_status != 2:  # 不是进行中
            self._widget.log_message("游戏已结束，不再继续分析")
            return

        if self._worker and self._worker.isRunning():
            return

        self._widget.log_message("自动继续分析...")
        self._start_analysis()

    def _start_analysis(self) -> None:
        """开始 LLM 分析"""
        if not self.llm_client:
            self._widget.log_message("请先配置 API 密钥")
            return

        if self._worker and self._worker.isRunning():
            self._widget.log_message("已有分析任务在运行")
            return

        # 重置用户停止标志
        self._user_stopped = False

        # 构建初始消息
        messages = self._build_initial_messages()

        # 创建并启动工作线程
        max_history = self.other_info.max_history_messages
        min_history = self.other_info.min_history_messages
        self._worker = LLMWorker(
            client=self.llm_client,
            registry=self.function_registry,
            messages=messages,
            max_history=max_history,
            min_history=min_history,
            config=self.other_info,
        )

        # 连接信号
        self._worker.log_signal.connect(self._widget.log_message)
        self._worker.chat_signal.connect(self._widget.add_chat_message)
        self._worker.finished_signal.connect(self._on_analysis_finished)
        self._worker.summary_signal.connect(self._widget.update_summary)

        self._widget.set_buttons_enabled(False)
        self._worker.start()

    def _stop_analysis(self) -> None:
        """停止 LLM 分析"""
        if self._worker and self._worker.isRunning():
            self.logger.info("用户请求停止 LLM 分析")
            self._widget.log_message("正在停止分析...")
            self._user_stopped = True
            self._worker.stop()
        else:
            self._widget.log_message("没有正在运行的分析任务")

    def _on_analysis_finished(self, success: bool, message: str) -> None:
        """分析完成回调"""
        if self._widget is None:
            return
        self._widget.set_buttons_enabled(True)

        if success:
            self._widget.update_status("分析完成")
        else:
            self._widget.update_status("分析中断")
        self._widget.log_message(message)

        # 如果是用户主动停止，不再自动继续分析
        if self._user_stopped:
            self._widget.log_message("用户已停止，不再自动继续")
            return

        # 无论成功还是失败，如果游戏状态是进行中，自动继续分析
        # 防止AI没有进行任何函数调用就结束
        if self._game_status == 2:  # playing
            self._widget.log_message("游戏进行中，1秒后继续分析...")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1000, self._auto_continue_analysis)

    def _build_initial_messages(self) -> List[Dict[str, Any]]:
        """构建初始消息列表"""
        messages = []

        # 系统提示词（写死在代码中）
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

        # 当前棋盘状态
        board_state = self._get_current_board_state()
        game_status = board_state.get('game_status', 'unknown')

        board_info = f"""当前棋盘状态:
- 行数: {board_state.get('rows', 0)}
- 列数: {board_state.get('cols', 0)}
- 剩余地雷: {board_state.get('mines_remaining', 0)}
- 游戏时间: {board_state.get('game_time', 0):.1f}秒
- 游戏状态: {game_status}
- 棋盘数据 (cells[row][col], -1=未揭开, 0-8=周围地雷数, F=标旗, M=踩到的地雷):
{json.dumps(board_state.get('cells', []), ensure_ascii=False)}

请分析当前局面并选择最佳操作。"""

        messages.append({"role": "user", "content": board_info})

        return messages

    # ═══════════════════════════════════════════════════════════════
    # 可调用的函数实现
    # ═══════════════════════════════════════════════════════════════

    def _execute_click_cell(self, col: int, row: int, button: str = "left") -> Dict[str, Any]:
        """执行点击格子操作

        Args:
            col: 列索引 (x 坐标, 从 0 开始)
            row: 行索引 (y 坐标, 从 0 开始)
            button: 鼠标按钮 ("left" 或 "right")
        """
        if not self.has_control_auth(MouseClickCommand):
            return {"success": False, "error": "无权限执行鼠标点击命令"}

        try:
            # button 转换: "left" -> 0, "right" -> 2
            button_map = {"left": 0, "right": 2, "middle": 1}
            button_value = button_map.get(button.lower(), 0)

            # 构建并发送鼠标点击命令
            click_cmd = MouseClickCommand(
                row=row,
                col=col,
                button=button_value,
            )
            self.send_command(click_cmd)

            self._widget.log_message(f"已点击格子: 行{row}, 列{col}, 按钮: {button}")
            return {
                "success": True,
                "message": f"格子点击已执行: 行{row}, 列{col}, {button}",
                "coordinates": {"row": row, "col": col},
                "button": button,
            }

        except Exception as e:
            error_msg = f"执行格子点击失败: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _execute_start_new_game(self, difficulty: str = None) -> Dict[str, Any]:
        """执行开始新游戏操作

        Args:
            difficulty: 游戏难度 ("easy", "medium", "hard")，默认使用配置中的 default_difficulty
        """
        if not self.has_control_auth(NewGameCommand):
            return {"success": False, "error": "无权限执行新游戏命令"}

        try:
            # 使用配置中的默认难度
            if difficulty is None:
                difficulty = self.other_info.default_difficulty

            # 难度映射: level 值
            # BEGINNER = 3, INTERMEDIATE = 4, EXPERT = 5
            difficulty_map = {
                "easy": 3,    # 初级
                "medium": 4,  # 中级
                "hard": 5,    # 高级
            }

            level = difficulty_map.get(difficulty, 4)

            # 清空当前棋盘状态
            self._current_board = None

            # 发送新游戏命令（使用 level 字段）
            new_game_cmd = NewGameCommand(level=level)
            self.send_command(new_game_cmd)

            # 获取对应的行列地雷数用于日志
            board_params = {
                "easy": (8, 8, 10),
                "medium": (16, 16, 40),
                "hard": (16, 30, 99),
            }
            rows, cols, mines = board_params.get(difficulty, (16, 16, 40))

            self._widget.log_message(
                f"已开始新游戏，难度: {difficulty} ({rows}x{cols}, {mines}雷)")
            return {
                "success": True,
                "message": f"新游戏已开始，难度: {difficulty}",
                "difficulty": difficulty,
                "level": level,
                "rows": rows,
                "cols": cols,
                "mines": mines,
            }

        except Exception as e:
            error_msg = f"开始新游戏失败: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _get_game_status_text(self) -> str:
        """获取游戏状态的文字描述"""
        status_map = {
            1: "ready",       # 准备
            2: "playing",     # 游戏中
            3: "win",         # 胜利
            4: "fail",        # 失败
            5: "show",        # 显示概率
            6: "study",       # 研究模式
            7: "display",     # 播放录像
            8: "showdisplay",  # 播放概率
        }
        return status_map.get(self._game_status, "unknown")

    def _get_current_board_state(self) -> Dict[str, Any]:
        """获取当前棋盘状态"""
        if self._current_board:
            result = self._current_board.copy()
            result["game_status"] = self._get_game_status_text()
            return result
        return {
            "rows": 0,
            "cols": 0,
            "cells": [],
            "mines_remaining": 0,
            "game_time": 0.0,
            "game_status": self._get_game_status_text(),
        }

    def _get_local_board(self, col: int, row: int, radius: int = 2) -> Dict[str, Any]:
        """获取局部棋盘区域

        Args:
            col: 中心列索引
            row: 中心行索引
            radius: 半径，默认2（返回5x5区域）

        Returns:
            局部棋盘数据，包含：
            - cells: 局部格子数据
            - center: 中心坐标（相对局部区域）
            - offset: 局部区域在全图的起始偏移
            - size: 局部区域大小
            - full_board_size: 全图大小
        """
        if not self._current_board or not self._current_board.get("cells"):
            return {
                "cells": [],
                "center": {"col": 0, "row": 0},
                "offset": {"col": 0, "row": 0},
                "size": {"rows": 0, "cols": 0},
                "full_board_size": {"rows": 0, "cols": 0},
                "error": "棋盘数据不可用",
            }

        full_cells = self._current_board.get("cells", [])
        full_rows = len(full_cells)
        full_cols = len(full_cells[0]) if full_cells else 0

        if full_rows == 0 or full_cols == 0:
            return {
                "cells": [],
                "center": {"col": 0, "row": 0},
                "offset": {"col": 0, "row": 0},
                "size": {"rows": 0, "cols": 0},
                "full_board_size": {"rows": 0, "cols": 0},
                "error": "棋盘为空",
            }

        # 计算局部区域边界
        start_row = max(0, row - radius)
        end_row = min(full_rows, row + radius + 1)
        start_col = max(0, col - radius)
        end_col = min(full_cols, col + radius + 1)

        # 提取局部格子
        local_cells = []
        for r in range(start_row, end_row):
            local_row = []
            for c in range(start_col, end_col):
                local_row.append(full_cells[r][c])
            local_cells.append(local_row)

        # 计算中心在局部区域中的位置
        center_col = col - start_col
        center_row = row - start_row

        return {
            "cells": local_cells,
            "center": {"col": center_col, "row": center_row},
            "offset": {"col": start_col, "row": start_row},
            "size": {"rows": len(local_cells), "cols": len(local_cells[0]) if local_cells else 0},
            "full_board_size": {"rows": full_rows, "cols": full_cols},
        }

    def _extract_board_data(self, event: BoardUpdateEvent) -> Dict[str, Any]:
        """从事件中提取棋盘数据

        game_board 值含义：
        - 0-8: 已揭开的数字格子
        - 10: 未揭开的格子
        - 11: 标旗的格子
        - 15: 踩到的地雷（红雷），游戏失败
        - 16: 未踩到的地雷（白雷）
        """
        game_board = event.game_board or []

        # 转换为 LLM 友好格式：-1=未揭开, 0-8=数字, F=标旗, M=地雷(踩到), m=地雷(未踩到)
        cells = []
        for row in game_board:
            row_data = []
            for cell in row:
                if cell == 10:  # 未揭开
                    row_data.append(-1)
                elif cell == 11:  # 标旗
                    row_data.append("F")
                elif cell == 15:  # 踩到的地雷（红雷），游戏失败
                    row_data.append("M")
                elif cell == 16:  # 未踩到的地雷（白雷）
                    row_data.append("m")
                else:  # 0-8 数字
                    row_data.append(cell)
            cells.append(row_data)

        return {
            "rows": event.rows,
            "cols": event.cols,
            "cells": cells,
            "mines_remaining": event.mines_remaining,
            "game_time": event.game_time,
        }

    def on_shutdown(self) -> None:
        """插件关闭时停止 Worker"""
        if self._worker and self._worker.isRunning():
            self.logger.info("正在停止 LLM Worker...")
            self._worker.stop()
            self._worker.wait(1)  # 等待最多3秒
        self._worker = None
