# Level 4: 控制授权系统

## 为什么需要控制授权？

为了防止多个插件同时发送冲突的控制指令，系统实现了**控制授权机制**：

- 每个**控制命令类型**只能授权给**一个插件**
- 未获得授权的插件发送该命令会被拒绝
- 授权变更时会通知相关插件

## 声明需要的控制权限

在 `PluginInfo` 中通过 `required_controls` 字段声明：

```python
from shared_types.commands import NewGameCommand, MouseClickCommand
from shared_types.enums import GameLevel

class MyPlugin(BasePlugin):
    
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            description="需要控制权限的插件",
            required_controls=[NewGameCommand],  # 👈 声明需要的控制权限
        )
```

## 可用的控制命令

| 命令类 | 说明 | 参数 |
|--------|------|------|
| `NewGameCommand` | 开始新游戏 | `rows`, `cols`, `mines` |
| `MouseClickCommand` | 模拟鼠标点击 | `row`, `col`, `button` |

## 检查授权状态

```python
def on_initialized(self) -> None:
    # 检查当前是否有权限
    has_auth = self.has_control_auth(NewGameCommand)
    if has_auth:
        self.logger.info("已获得 NewGameCommand 权限")
    else:
        self.logger.warning("未获得 NewGameCommand 权限")
```

## 响应授权变更

覆写 `on_control_auth_changed` 方法：

```python
def on_control_auth_changed(
    self,
    command_type: type,
    granted: bool,
) -> None:
    """
    控制权限变更回调
    
    Args:
        command_type: 命令类型
        granted: True 表示获得权限，False 表示失去权限
    """
    if command_type == NewGameCommand:
        if granted:
            self.logger.info("获得了控制权限")
            self.run_on_gui(self._widget.enable_controls, True)
        else:
            self.logger.warning("失去了控制权限")
            self.run_on_gui(self._widget.enable_controls, False)
```

## 发送控制命令

```python
def _start_new_game(self) -> None:
    # 自定义尺寸必须显式指定 level=GameLevel.CUSTOM.value
    command = NewGameCommand(
        level=GameLevel.CUSTOM.value, rows=16, cols=30, mines=99,
    )

    # 方式一：直接发送（无权限时会被拒绝）
    self.send_command(command)

    # 方式二：检查权限后再发送
    if self.has_control_auth(NewGameCommand):
        self.send_command(command)
    else:
        self.logger.warning("没有控制权限")
```

## 用户授权操作

用户通过插件管理器管理授权：

1. 打开插件管理器
2. 点击工具栏的 **"🔐 控制授权"** 按钮
3. 选择要授权的控制类型
4. 从下拉列表中选择插件
5. 确认后生效

授权配置会持久化到 `data/control_authorization.json`。

## 相关 API

| 方法/属性 | 说明 |
|-----------|------|
| `has_control_auth(command_type)` | 检查是否有该控制类型的权限 |
| `on_control_auth_changed(cmd_type, granted)` | 权限变更回调（覆写） |
| `PluginInfo.required_controls` | 声明需要的控制权限 |
| `send_command(command)` | 发送控制命令 |
