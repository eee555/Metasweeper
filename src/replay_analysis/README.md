# Replay Analysis 重构计划

## 目标

当前事件分析以函数规则为主：每个规则接收 `ReplayEventContext`，返回 `ReplayEventAnnotation`。这套方式适合无状态规则，但对需要跨事件累计状态的事件不够清晰，例如 `标雷` 需要维护已有 flag 和后续 chord 分摊，`连击` 需要维护连续 lce 序列。

后续重构目标是：

- 使用 `ReplayEvent` 作为所有事件类型的基类。
- 每类事件定义一个 `ReplayEvent` 子类，保存该事件的结构化数据、状态、坐标和渲染信息。
- 每类事件解析由一个 manager 管理内部状态。
- manager 顺序接收 `ReplayEventContext`，在识别到事件时发出对应 `ReplayEvent`。
- `possibility_board`、`prior_board` 等昂贵或特定的数据只由需要它们的 manager 维护，不放进所有事件的通用路径。

## 目标模型

### ReplayEvent

`ReplayEvent` 是所有本地事件的基类，替代当前散落在各规则中的 `ReplayEventAnnotation` 构造逻辑。

建议字段：

- `event_index`: 事件挂载到的 `video.events` 下标。
- `time`: 事件发生时间。
- `event_type`: 已翻译的事件类型文本，或可延迟翻译的 source key。
- `coordinate`: 表格“坐标”列显示的主坐标，可为空。

建议方法：

- `type_text() -> str`: 返回当前语言下的事件类型。
- `detail_text() -> str`: 返回当前语言下的详情文本。
- `severity() -> str`: 返回 `success`、`info`、`warning`、`error`。
- `highlight_cells() -> tuple[tuple[int, int], ...]`: 返回行悬浮时高亮的格子列表。
- `to_annotation() -> ReplayEventAnnotation`: 兼容现有 UI，迁移期用于输出到表格。

### 事件子类

当前四类事件建议拆成：

- `GuessEvent`
  - 数据：`pluck`、`pluck_diff`、`mine_probability`、`global_min_probability`、`non_frontier_probability`。
  - 高亮：猜雷格。

- `OnePointFiveClickEvent`
  - 数据：右键按下和左键按下间隔、成功标雷和成功 chord 间隔。
  - 高亮：`rce` 格和 `dce` 格。

- `ComboClickEvent`
  - 数据：连击长度、lce 间隔最大值、最小值、平均值。
  - 高亮：连击序列全部格。

- `FlagEvent`
  - 数据：分摊到该 flag 的 chord 数量、分摊到该 flag 的 `bbbv_solved` 增量。
  - 高亮：flag 格和分摊给它的周围 chord 格。

## Manager 模型

每个事件类型对应一个 manager。manager 是有状态对象，顺序消费 context。

建议接口：

```python
class ReplayEventManager:
    def reset(self, start_context: ReplayEventContext) -> None:
        ...

    def handle(self, context: ReplayEventContext) -> Iterable[ReplayEvent]:
        ...
```

分析入口只负责：

1. 创建 managers。
2. 按 `video.events` 顺序构造 `ReplayEventContext`。
3. 使用开始事件 context 初始化每个 manager。
4. 从开始事件之后，把 context 依次传给每个 manager。
5. 收集 manager 发出的 `ReplayEvent`。
6. 按 `event_index` 汇总后交给 UI。

## 状态归属

`ReplayEventContext` 应保持轻量，只包含当前 record 的基础信息和必要 unwrap 结果。不要在 context 中提前计算所有 manager 可能用到的数据。

具体归属建议：

- `GuessEventManager`
  - 维护上一鼠标事件的 pluck；产生猜雷事件时，从当前记录的 `prior_game_board` 读取点击前局面和 `poss` 概率矩阵。
  - 负责猜雷概率、全局最小概率、非前沿概率计算。

- `FlagEventManager`
  - 维护当前已有 flag 列表。
  - 维护每个 flag 的累计 chord 分摊和 `bbbv_solved` 分摊。
  - 遇到 `dce` 增长时，按事件顺序把增量均分给周围已有 flag。

- `ComboClickEventManager`
  - 维护当前连续 lce 序列。
  - 只有 `rce` 和 `dce` 增长打断 lce 序列。
  - 当前序列结束且长度至少为 3 时发出 `ComboClickEvent`。

- `OnePointFiveClickEventManager`
  - 维护最近的有效鼠标动作。
  - 识别 `rc -> lc/cc -> release with dce+1` 模式。

## 翻译策略

事件对象不应永久保存已翻译文本，否则语言切换后会出现旧语言残留。

推荐做法：

- 事件对象保存稳定的结构化数据。
- `type_text()` 和 `detail_text()` 每次调用时通过 `QCoreApplication.translate(...)` 生成当前语言文本。
- UI 语言切换时重建表格行即可，不需要重新解析整个录像。

迁移完成后，当前 `FlagEventManager` 这类语言相关缓存可以删除。

## 迁移步骤

1. 在 `core.py` 中新增 `ReplayEvent` 和 `ReplayEventManager` 基础类。
2. 保留 `ReplayEventAnnotation` 作为 UI 兼容层，新增 `ReplayEvent.to_annotation()`。
3. 将 `guess.py` 改为 `GuessEvent` + `GuessEventManager`。
4. 将 `one_point_five_click.py` 改为 `OnePointFiveClickEvent` + `OnePointFiveClickEventManager`。
5. 将 `combo_click.py` 改为 `ComboClickEvent` + `ComboClickEventManager`。
6. 将 `flag.py` 改为 `FlagEvent` + `FlagEventManager`，移除全局 cache。
7. 修改 `analyse_replay_events()`，从规则函数注册模型迁移到 manager 列表模型。
8. 修改控制面板语言切换逻辑：语言变化时只重新渲染已有 `ReplayEvent`，不重新跑解析。
9. 删除旧的 rule 注册 API，或保留一层临时适配直到所有事件迁移完成。

## 验收标准

- 打开录像后四类事件数量与重构前一致。
- 事件表的类型、详情、状态颜色、坐标、高亮行为与重构前一致。
- 切换语言后，表头、事件类型、事件详情全部更新，不重新调用 `ms_toollib` 的重分析接口。
- `GuessEventManager` 之外的 manager 不读取 `possibility_board`。
- 不需要 `prior_board` 的 manager 不读取或保存 `prior_board`。
