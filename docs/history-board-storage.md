# 历史记录 `board` 列的紧凑存储约定

> 适用版本：历史记录插件引入 `board_codec` 之后。
> 相关代码：`src/plugins/history/board_codec.py`

## 为什么要改

`history.board` 原本存「带数字的完成局面」JSON 文本
（形如 `[[0,1,-1,1],[1,2,2,-1],...]`）。对 540 条真实记录实测：

| 项 | 大小 |
|---|---|
| 原始 JSON 文本 | 143,795 B（平均 266 B/条） |
| 只存雷图（1 bit/格 + 4 B 尺寸头） | 9,950 B |

数字格可由雷图通过 `ms_toollib.cal_board_numbers()` 无损推导，
540/540 条实测还原出**完全相同**的 JSON，因此数字部分全是冗余。

## 物理存储格式

`history.board` 列现在是一个 **BLOB**（不再是 TEXT）：

```
[2B row (小端 uint16)][2B col (小端 uint16)][ceil(row*col/8) B 位图]
```

位序：第 `i*col+j` 个格子对应 `bits[i//8]` 的 `7 - i%8` 位，1 表示雷。
这与 evf 标准里的雷图位序一致。

## 读取约定（必须遵守）

> **`SELECT * FROM history` 拿到的 `board` 是 `bytes`，不是 JSON 字符串。**

需要 JSON 文本时，用 SQLite 自定义函数展开：

```sql
SELECT replay_id, py_board_json(board) AS board FROM history;
```

对局面做字符串比较 / `LIKE` 时**必须**展开，否则会作用在二进制上，
得到无意义的结果且不会报错：

```sql
SELECT COUNT(*) FROM history
WHERE py_board_json(board) LIKE '%[0,0%';
```

自定义计算列若引用 `board`，表达式里也要写 `py_board_json(board)`。

## 自动注册的函数

`plugins.history.db.db_connection()` 在**每个** SQLite 连接上注册以下
函数（与用户自定义的 `py_` 脚本无关，始终可用）：

| 函数 | 作用 |
|---|---|
| `py_board_json(x)` | 雷图 BLOB → JSON 文本；传入旧 JSON 字符串时**原样返回**（兼容未迁移数据） |
| `py_board_blob(x)` | JSON 文本 → 雷图 BLOB；解析失败时原样返回 |
| `py_board_is_blob(x)` | 判断是否已是紧凑 BLOB（迁移用），返回 1/0 |

因此 `HistoryService.raw_query` / `raw_query_one` 的调用方可直接使用它们，
无需额外配置。

## 插件内部已经处理的地方

第三方插件和调用方**不需要**关心以下路径，历史记录插件内部已统一展开：

| 路径 | 处理 |
|---|---|
| 表格 `load_data` 的 SELECT | `board` 字段替换为 `py_board_json("board") AS "board"` |
| 计算列子查询 `build_subquery_sql` | 显式列出物理列，`board` 用 UDF 展开并沿用列名 |
| 过滤 `build_where` / 排序 `build_order_by` | `board` 字段自动包 `py_board_json("board")` |
| 悬浮局面预览 `parse_board()` | 拿到的是展开后的 JSON 字符串 |
| 复制 JSON `export_row_json` | 从表格模型取展开后的值 |
| 写入 `_on_video_save` | `board_json_to_blob()` 转成 BLOB 后落盘 |

## 不受影响的部分

- `history` 表**结构**、主键、`AUTOINCREMENT`、全部 4 个索引均未改动，
  `cursor.lastrowid` 写入路径正常。
- 除 `board` 外的所有列（rtime / level / bbbv / mode / ...）类型与语义不变。
- 不涉及 `board` 的聚合、分组、过滤、排序、分页、`COUNT(*) OVER()` 结果不变。
- 索引命中情况不变（UDF 只作用于 SELECT/WHERE 的 board 列，
  过滤条件仍走 `idx_history_level` 等索引）。

## 兼容与回退

- `py_board_json` 对 `str` 输入原样返回，因此**旧库里尚未迁移的 JSON 文本
  board 仍可正常读取**，可平滑灰度迁移。
- `board_json_to_blob` 解析失败返回 `None`，`_on_video_save` 会保留原值，
  不会静默丢弃数据。
- 迁移函数 `migrate_board_to_blob()` 幂等：已压缩的行（`py_board_is_blob`=1）
  会跳过。

## 迁移

```python
from plugins.history.board_codec import migrate_board_to_blob
from plugins.history.db import db_connection

with db_connection(db_path) as conn:
    n = migrate_board_to_blob(conn)
    conn.commit()
    conn.execute("VACUUM")
```

迁移会逐条校验 `py_board_json(压缩后) == 原 JSON`，任一条不一致即抛错并
回滚，不会留下半迁移状态。
