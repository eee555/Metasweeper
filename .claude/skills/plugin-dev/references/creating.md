# 创建新插件流程

## 重要：必须使用脚本创建

**必须使用 `python {skills_path}/plugin-dev/scripts/create_plugin.py` 脚本来创建插件！**

禁止手动编写插件代码，必须通过脚本生成。

---

## 脚本使用指南

### 脚本路径

```
python {skills_path}/plugin-dev/scripts/create_plugin.py
```

### 命令 1：discover（发现可用类型）

```bash
python {skills_path}/plugin-dev/scripts/create_plugin.py discover
```

返回项目中的可用事件类型和命令类型：

```json
{
    "environment": "dev",
    "plugins_dir": "src/plugins",
    "shared_types_dir": "src/shared_types",
    "events": [{ "name": "BoardUpdateEvent", "description": "..." }],
    "commands": [{ "name": "NewGameCommand", "description": "..." }]
}
```

### 命令 2：create（创建插件）

```bash
python {skills_path}/plugin-dev/scripts/create_plugin.py create --name <名称> [选项]
```

**必选参数：**
| 参数 | 说明 |
|------|------|
| `--name` | 插件名称（英文，下划线分隔，如 `my_plugin`） |

**可选参数：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--description` | "" | 插件描述 |
| `--version` | "1.0.0" | 版本号 |
| `--author` | "" | 作者名称 |
| `--window-mode` | "TAB" | 窗口模式：`TAB`、`DETACHED`、`CLOSED` |
| `--icon-color` | "#4CAF50" | 图标颜色（十六进制） |
| `--icon-char` | 插件名首字母 | 图标字符 |
| `--events` | "" | 订阅的事件，逗号分隔（如 `BoardUpdateEvent,VideoSaveEvent`） |
| `--commands` | "" | 需要的控制权限，逗号分隔（如 `NewGameCommand`） |
| `--config` | True | 是否需要配置系统（默认启用） |
| `--service` | False | 是否需要服务接口 |

---

## 创建流程

### 步骤 1：执行 discover 检测环境

```
python {skills_path}/plugin-dev/scripts/create_plugin.py discover
```

### 步骤 2：收集插件信息

使用 `ask_user_question` 工具询问：

1. **基本信息**

```json
{
    "question": "请输入插件名称（英文，下划线分隔，如 my_plugin）:",
    "header": "插件名称"
}
```

2. **描述信息**

```json
{
    "question": "请输入插件描述:",
    "header": "描述"
}
```

3. **作者信息**

```json
{
    "question": "请输入作者名称:",
    "header": "作者"
}
```

4. **功能选项**

```json
{
    "question": "插件需要哪些功能?",
    "header": "功能选项",
    "options": [
        { "label": "GUI 界面", "description": "插件需要一个可视化界面" },
        { "label": "订阅事件", "description": "监听游戏事件（如游戏结束）" },
        { "label": "发送指令", "description": "控制主进程（如开始新游戏）" }
    ],
    "multiSelect": true
}
```

### 步骤 3：执行脚本创建插件

根据收集的信息构建命令并执行：

**示例：创建带 GUI 和事件的插件**

```bash
python {skills_path}/plugin-dev/scripts/create_plugin.py create \
    --name test_game \
    --description "游戏测试插件" \
    --author developer \
    --window-mode TAB \
    --icon-color "#2196F3" \
    --icon-char T \
    --events BoardUpdateEvent,VideoSaveEvent,GameStatusChangeEvent
```

### 步骤 4：验证创建结果

创建完成后验证语法：

```bash
python -m py_compile src/plugins/<plugin_name>/plugin.py
```

脚本会在插件目录默认生成一个空的 `README.md`（仅含标题骨架），可通过插件管理器右键菜单「查看 README」打开。

- 生成位置：`src/plugins/<name>/README.md`

然后告知用户：

1. 插件文件位置
2. 已生成的 `README.md`（可在插件目录下自行填充内容）
3. 提醒重启插件管理器以加载新插件

---

## 示例交互流程

```
用户: 帮我创建一个游戏测试插件

助手: 先执行 discover 检测环境...
    python {skills_path}/plugin-dev/scripts/create_plugin.py discover

助手: 环境正常。可用事件：BoardUpdateEvent, VideoSaveEvent...

助手: [使用 ask_user_question 询问插件名称]
用户输入: test_game

助手: [询问描述]
用户输入: 游戏测试插件

助手: [询问功能选项]
用户选择: GUI 界面, 订阅事件

助手: 执行创建脚本...
    python {skills_path}/plugin-dev/scripts/create_plugin.py create \
        --name test_game \
        --description "游戏测试插件" \
        --author developer \
        --events BoardUpdateEvent,VideoSaveEvent

助手: 验证语法...
    python -m py_compile src/plugins/test_game/plugin.py

助手: 插件已创建！
    - src/plugins/test_game/__init__.py
    - src/plugins/test_game/plugin.py
    - src/plugins/test_game/widgets.py

    请重启插件管理器以加载新插件。
```
