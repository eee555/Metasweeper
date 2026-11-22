# 开发计划

计划开发：
- 暂无计划中的开发内容，根据issue动态决定。

不计划开发：
- 移动端的扫雷。
- 在本地统计个人数据的功能。
- 安装程序和启动界面。
- 扫雷游戏以外的游戏、无猜模式以外的扫雷模式。
- 非标准且花哨的ui、任何多余且匪夷所思的选项。
- 任何用于在其他软件作弊以取得异常短的时间的成绩的设计。
- 扫码收费以解锁某功能的功能。

# 其他
- 根据开发者的习惯，代码接受中文、英文等主流语言的注释。




# Development Plan

Planned Development:

* Currently no planned features. Future development will be determined dynamically based on issues.

Not Planned for Development:

* Minesweeper for mobile devices.
* Features for tracking personal statistics locally.
* Installers and launch screens.
* Games other than Minesweeper, or Minesweeper modes other than no-guessing mode.
* Non-standard or flashy UI, or any unnecessary or bizarre options.
* Any designs intended to cheat in other software to achieve abnormally short completion times.
* Features that require scanning a QR code and paying to unlock functionality.

# Other

* Following the developer’s habits, the code accepts comments in Chinese, English, and other major languages.

# 推送前测试

提交时不会自动运行测试。推送前需确认测试通过；仓库的 `.githooks/pre-push` 会运行完整 `pytest tests/`，失败时阻止推送。克隆仓库后启用一次：

```powershell
git config core.hooksPath .githooks
```

推送钩子优先使用仓库的 `.venv`，并默认设置 `QT_QPA_PLATFORM=offscreen`。CI 也会在 push 和 pull request 时运行完整测试套件。

# Tests Before Push

Commits do not run tests automatically. Before pushing, confirm the tests pass; the repository's `.githooks/pre-push` runs the full `pytest tests/` suite and blocks the push if it fails. Enable the hook once after cloning:

```powershell
git config core.hooksPath .githooks
```

The pre-push hook prefers the repository's `.venv` and defaults `QT_QPA_PLATFORM` to `offscreen`. CI also runs the full test suite on pushes and pull requests.

