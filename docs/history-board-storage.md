# 历史记录 `board` 列存储约定

相关实现见 `src/plugins/history/board_codec.py`。

## 当前格式

`history.board` 使用按行优先排列的 ASCII 文本，每格一个字符：`*` 表示雷，
`0` 至 `8` 表示周围雷数。行数和列数分别保存在同一记录的 `row` 和
`column` 字段中；正常数据的字符串长度为 `row * column`。
例如 `[[-1,-1,-1],[2,3,2],[0,0,0]]` 存为 `***232000`。

已迁移数据可直接读取和过滤：

```sql
SELECT replay_id, "row", "column", board FROM history WHERE board LIKE '%***%';
```

计算列、过滤和排序直接使用 `board`。表格的局面预览使用行列数还原二维
棋盘；复制记录的 JSON 时，`board` 字段仍是 ASCII 文本。

## 旧数据与迁移

旧记录可能是二维 JSON 文本或雷图 BLOB。BLOB 格式为两个小端 uint16
行列数，后接每格一位的雷图，位序从每字节高位开始。插件启动时会在后台
调用 `migrate_board_to_ascii()`，将可安全转换且尺寸匹配的记录逐批转为
ASCII；无法转换的记录保留原值。已是 ASCII 的记录会跳过，因此可以重试。
迁移期间，直接查询或过滤 `board` 可能遇到不同格式。

`db_connection()` 在每个连接注册兼容函数：

| 函数 | 作用 |
|---|---|
| `py_board_ascii(board, row, column)` | 将旧 JSON、旧 BLOB 或 ASCII 转成 ASCII，转换失败返回 NULL |
| `py_board_is_ascii(board)` | 判断是否为 ASCII 棋盘字符串 |
| `py_board_is_blob(board)` | 判断是否符合旧 BLOB 的尺寸和长度 |
| `py_board_json(board)` | 将旧 BLOB 转成 JSON；字符串原样返回，包括新的 ASCII 文本 |
| `py_board_blob(board)` | 将旧 JSON 转成 BLOB；转换失败时返回原值 |

例如，在迁移期间需要按 ASCII 格式查询时：

```sql
SELECT replay_id, py_board_ascii(board, "row", "column") AS board FROM history;
```

`py_board_json` 不会把 ASCII 还原成二维 JSON，因为它没有行列参数。
Python 调用方可用 `board_ascii_to_matrix(board, row, column)` 还原棋盘。
