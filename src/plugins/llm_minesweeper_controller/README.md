# 元扫雷 MCP 服务

将原 LLM 反控扫雷插件迁移为本机 MCP 服务。包名
`llm_minesweeper_controller`、主类 `LlmMinesweeperControllerPlugin` 和配置类名保持不变，
显示名及授权身份改为“元扫雷 MCP 服务”。旧身份的控制授权不会自动转移，用户必须重新授权。

不再提供内置 LLM API 客户端、API 密钥配置、聊天、历史压缩、自动分析或自动续跑。
新增传输逻辑只使用 Python 标准库，复用项目现有 Qt 和官方插件 SDK，不新增第三方依赖。
遵守项目 [公平游戏策略](../../../AI_AGENT_POLICY.md)：不读取隐藏棋盘、不绕过权限或辅助标记。

## 启动与连接

1. 在插件管理器中加载插件。默认服务停止，加载、连接或初始化客户端均不会自动开始游戏。
2. 唯一配置为整数 `port`，默认 `8765`，范围 `1..65535`。手动启动后监听
   `http://127.0.0.1:<port>/mcp`，不监听局域网地址。
3. 将界面生成的提示词交给现有 agent，为其现有 MCP 配置添加 Streamable HTTP endpoint，保留其余配置。
   不安装包，不配置 stdio 子进程，不自动玩游戏。客户端必须已经支持 HTTP MCP。
4. 用户明确决定是否授权 `MouseClickCommand`、`NewGameCommand`，并在主进程高级设置中打开
   对应控制开关及棋盘事件开关。插件检查官方 `has_control_auth()`，主进程再次检查控制开关。
5. 停止服务会取消未执行请求、关闭连接并释放监听端口。每次重新启动会作废旧会话。

服务不校验访问令牌，安全边界依赖仅监听本机回环地址与严格的 Host／Origin 校验。
只应在可信的本机环境使用；不要把该端口转发到局域网或公网。

若端口被占用，启动进入 `error`，不会改用其他地址或自动扫描端口。
更换端口必须先停止。旧 API 配置不再读取，也不迁移密钥或授权。

## 查询协议

查询是插件主动向主进程取数的第三类消息，与命令、事件并列：

```python
# 主进程注册（自动在主线程执行）
bridge.register_query_handler(GetBoardStateQuery, handle_board_state)

# 插件调用（强类型，IDE 可补全）
result = self.query(GetBoardStateQuery())
if isinstance(result, BoardStateResult) and result.success:
    print(result.cells, result.game_status)
```

- 定义在 `shared_types/queries.py`：请求继承 `BaseQuery`，响应继承 `BaseQueryResult`；
- 每个查询对应一个具体结果类，字段有类型提示；
- 与命令共用控制通道，通过 msgspec 的 `type` 标记区分，不新增端口；
- 不进入 `ControlAuthorizationManager`。`get_board_state` 与 `get_game_status` 受主进程
  `board_update` 权限约束；`get_game_context` 不含棋盘格子，不受该权限限制；
- 未注册处理器的查询返回 `BaseQueryResult(success=False, error="No handler ...")`，不会静默超时。

**实现约束**：实时对局的 `ui.label.ms_board` 是尚未解析的 `ms.BaseVideo`，读取
`rtime`、`bbbv_solved` 等统计字段会在 `ms_toollib` 的 Rust 层直接崩溃（退出码
`0xC0000409`），`try/except` 无法捕获。查询处理器只读取已验证安全的字段
（`game_board`、`level`、`time`、`bbbv`、`is_official`、`is_fair`、`software`），
统计字段仅在已解析的录像对象上读取；实时对局的 `rtime` 返回 `0.0`、`bbbv_solved` 为 0、
`progress` 为 `null`。新增查询字段前请先单独验证该属性不会崩溃。

## 工具

| 工具 | 参数 | 行为 |
| --- | --- | --- |
| `get_board_state` | 无 | 主动请求主进程的可见棋盘快照；失败时回退到最近一次官方事件并标注 `source="cache"` |
| `get_game_status` | 无 | 主动请求状态、计时、剩余雷数与局面参数；失败时回退到缓存 |
| `get_game_context` | 无 | 主动请求状态、参数、3BV 进度、官方/公平标志与当前已开启的控制权限 |
| `click_cell` | `clicks` 数组，或原有 `row`, `col`, `button="left"` | 单次最多 128 项；行列从零开始；按钮限 `left`、`middle`、`right` |
| `start_new_game` | `difficulty="medium"` | 难度限 `easy`、`medium`、`hard` |

### 批量点击

保留工具名 `click_cell`，以下为 `tools/call` 的参数：

```json
{
  "name": "click_cell",
  "arguments": {
    "clicks": [
      {"row": 0, "col": 1},
      {"row": 2, "col": 3, "button": "right"},
      {"row": 4, "col": 5, "button": "middle"}
    ]
  }
}
```

旧参数 `{"row": 0, "col": 1, "button": "left"}` 仍可用，但不能与 `clicks` 混用。
数组必须有 1..128 项；所有项的字段、类型、按钮及初始棋盘边界均在首次点击前完整预检。
批量必须获得实时可见棋盘，不能用缓存代替。每项按顺序重新检查状态和授权，发送原有
`MouseClickCommand` 并等待匹配的 `CommandResponse`；下一项前再次刷新棋盘。

结果中的 `requested` 为请求项数，`completed` 只统计主进程明确确认成功的项；`results`
按顺序保留逐项结果，`stopped_index` 是首个未确认成功项的零基下标，全部成功时为 `null`。
`unattempted` 表示尚未进入逐项结果的后续项数；明确拒绝或本地阻止的项可能已包含在
`results` 内，但不会计入 `completed`。预检失败和排队取消时完成数为零、结果为空。

首个失败、确认未知、取消、会话关闭、服务停止、授权撤回、实时棋盘不可用、对局结束，
或观察到棋盘失效、尺寸变化、计时回退、回到准备状态时停止。部分完成为 `outcome="partial"`，
发送后无有效确认则为 `unknown`，全部成功为 `confirmed`，没有执行为 `not_executed`。
取消与响应确认通过同一把锁协调；停止时保留已接受的确认，不能将“已发送”计为完成。

**不是原子事务**：已经确认的点击不回滚，已经发送的点击无法撤回，不自动重试或续跑。
批次仍受工具总期限八秒约束，不会按项延长期限；大批次也可能只完成一部分。
继续前必须检查 `completed`、`results`、`stopped_index` 并重新读取局面。
协议没有跨进程棋盘标识或期望版本，无法保证识别未观察到的同尺寸换局，也无法消除
最后一次检查与主进程执行之间的竞态；不能把插件侧检查视为跨进程原子保护。

三个只读工具通过查询协议（`GetBoardStateQuery`、`GetGameStatusQuery`、`GetGameContextQuery`）主动向主进程
取值，结果是与请求一一对应的强类型结果类（`BoardStateResult` 等），使用与事件推送相同的可见数据，
不读取隐藏地雷。查询不是控制指令，不进入插件控制授权；`get_board_state` 与 `get_game_status`
仍受主进程 `board_update` 权限约束，权限关闭时返回错误。`get_game_context` 只返回状态、参数、
统计与控制权限，不包含任何棋盘格子，因此不受 `board_update` 限制，可在权限关闭时用于判断
应当开启哪些开关。主动请求成功时结果带 `source="live"`；
请求失败或主进程返回无效数据时，棋盘与状态回退到最近一次官方事件并标注 `source="cache"`，
上下文查询没有缓存回退。

坐标只接受整数，明确拒绝布尔值、浮点值、字符串、负数和越界值；拒绝未知参数、按钮和难度。
只有已知的准备、胜利、失败状态允许请求新游戏，进行中、研究、录像及未知状态均拒绝重开。
所有控制只通过原 SDK 指令和同步 `CommandResponse` 返回确认结果，主进程拒绝时返回工具错误，
不把“已发送”说成“已执行”。原 SDK 和主进程负责辅助及成绩来源标记，插件不改写这些机制。

没有收到有效棋盘或状态事件时返回“不可用”，不会构造虚假空棋盘。状态名称直接取自
`GAME_EVENT_STATE_MAP`，包括映射到同一事件值的游戏状态。格子 `-1` 表示未揭开，`0..8` 为数字，
`F` 为可见旗帜，`X` 为可见错旗，`M`、`m` 只来自事件中已显示的地雷；未知格子值按未揭开处理。
不会请求隐藏棋盘、真实地雷分布或概率。缓存不是实时结果，关闭事件推送也不会使旧缓存自动更新。

成功动作后使缓存失效，等待新棋盘事件再操作。SDK 等待超时或没有确认时返回 `outcome="unknown"`，
不得自动重试；排队中超时、停止或取消则为 `not_executed`。已经开始的主进程命令无法撤回，
网络断连本身也不等于取消。

## 协议与限制

已核对并实现的协议范围仅为 **2025-11-25** 的工具服务和 Streamable HTTP JSON 响应子集，
不承诺新版、旧 HTTP+SSE 或 stdio 兼容，不宣称完整 MCP 功能认证。

- 支持 `initialize`、`notifications/initialized`、`ping`、`tools/list`、`tools/call`。
- 初始化返回随机 `Mcp-Session-Id`；后续请求携带该会话及协商的 `MCP-Protocol-Version`。
  不支持的请求版本会协商为 `2025-11-25`，客户端不支持此版本时应断开；不支持的版本请求头返回 400。
  未提供版本头时可从已知会话推断版本。
- POST 使用 UTF-8 JSON，`Content-Type: application/json`，`Accept` 同时包含
  `application/json` 和 `text/event-stream`。接受的通知返回空体 202，不执行带工具名的通知。
- HTTP 响应为单个 JSON 对象；GET 返回 405，不提供 SSE。DELETE 终止会话并取消其未执行请求。
- JSON-RPC 错误包括 `-32700`、`-32600`、`-32601`、`-32602`；未就绪及会话上限使用 `-32000`。
  有效请求保留 ID，无法识别 ID 时省略它；通知不返回 JSON-RPC 响应。工具输入或执行失败返回
  `isError: true`，同时提供文本及 `structuredContent`。
- 支持 `notifications/cancelled` 取消未执行的工具请求。不提供 tasks、资源、提示词服务、sampling、
  进度推送、恢复流、OAuth 发现。
- Host 必须为 `127.0.0.1:<port>`；Origin 可缺省，但存在时必须为相同 HTTP origin。
  不开放 CORS，不允许转发代理、任意 Host 或通配 Origin，拒绝重复安全头及 Transfer-Encoding。
- 最多八个 HTTP 连接及八个排队请求，超过连接限制直接关闭额外连接；最多 32 个会话，
  需要 DELETE 或重启释放。POST/DELETE 全局每秒最多 32 次，超额返回 429。
- 请求体最多 64 KiB，解析后的请求头最多 16 KiB，棋盘最多 65536 格。
  请求头与正文总读取期限三秒，响应写入期限三秒，SDK 等待三秒，工具总等待八秒。

官方参考：
[传输](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)、
[生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、
[工具](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)、
[基础消息](https://modelcontextprotocol.io/specification/2025-11-25/basic)。

## 界面

界面只有一个运行日志式的最小控制页，由 `widgets.McpControlWidget` 提供：

- 一个启动/停止按钮，随真实状态切换；启动中、停止中暂时禁用，避免重复操作。
- 一个监听端口输入框，默认 `8765`，运行期间锁定；更换端口必须先停止。
- 一行状态标签，显示已停止、运行地址或简短错误。
- 一个只读配置提示词文本框和复制按钮。仅在用户点击时写入剪贴板，不自动复制。

控件在工作线程之外的主线程创建，插件状态通过显式 queued 信号更新界面，界面请求同样以 queued
连接投递给插件线程。启动失败不会自动改端口或重试。

## 界面接口

```python
widgets.McpControlWidget(parent=None)
start_requested(int)
stop_requested()
set_port(int)
@Slot(object)
set_service_state(dict)
```

插件 `service_state_changed(object)` 以显式 queued 连接投递到控件的 `set_service_state`。
两个 GUI 请求信号以显式 queued 连接到插件 `start_mcp(port)` / `stop_mcp()`。
状态字典固定提供 `state`、`port`、`endpoint`、`prompt`、`error`；状态为
`stopped/starting/running/stopping/error`。只有 `running` 携带 endpoint 和配置提示词，
其他状态清空它们。

## 通信审查与验证边界

HTTP 线程只解析协议和等待结果，不直接访问 GUI、棋盘或共享 ZMQ。
`RequestBridge` 将工具排队到插件私有 `CommandIO` 线程串行执行；其 ZMQ socket 的创建、
发送、接收、关闭均由该线程负责。控制仍使用官方命令、响应序列化和授权管理器，
每次发送前重查授权，不使用其他插件共享的 socket。进度是内部取消快照，不是 MCP 进度推送。

**通信审查边界：** 私有 I/O 线程不修复项目其他插件共享 `ZMQClient` 的线程所有权风险。
真实主进程与 agent 客户端互操作、断连及停止时序仍需通信专家实机审查。
本次批量功能不修改 SDK、ZMQ 库、共享类型或主进程协议，也未启动真实游戏控制。

**跨进程竞态：** “不覆盖进行中游戏”检查基于最新收到的官方状态事件。现有 `NewGameCommand`
不支持主进程原子检查期望状态或棋盘版本，故事件延迟或用户同时开始游戏时仍存在竞态；
不能把插件侧检查描述为跨进程原子保证。修复需要通信与主进程接口审查，不在本次修改范围内。

聚焦测试位于 `tests/test_mcp_controller.py`，使用假 SDK、标准库 HTTP 临时端口、模拟 ZMQ
主进程和 Qt 测试控件，不连接真实游戏。涵盖协议、安全、界限、批量预检与顺序、权限撤回、
棋盘失效、确认与取消竞态、未知结果、排队取消及端口释放。
GUI 实际线程联调、真实 agent 客户端互操作和共享 ZMQ 实机安全性仍需另行验证。