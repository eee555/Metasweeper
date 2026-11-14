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

# 提交与推送前测试

提交代码或推送分支前，必须先让测试通过。最低要求是本次改动涉及的测试全部通过；若其余测试也可运行，应运行完整测试套件并确保全部通过。测试失败时不得提交或推送。

本仓库提供 `.githooks/pre-commit` 和 `.githooks/pre-push`，两者都会运行 `pytest tests/`。克隆仓库后启用一次：

```powershell
git config core.hooksPath .githooks
```

钩子优先使用仓库的 `.venv`，并默认设置 `QT_QPA_PLATFORM=offscreen`。CI 也会在 push 和 pull request 时运行完整测试套件。

# Tests Before Commit and Push

All tests relevant to the changed code must pass before committing or pushing. Run the full test suite and require all tests to pass whenever the rest of the suite is runnable. Do not commit or push while applicable tests are failing.

The repository provides `.githooks/pre-commit` and `.githooks/pre-push`; both run `pytest tests/`. Enable them once after cloning:

```powershell
git config core.hooksPath .githooks
```

The hooks prefer the repository's `.venv` and default `QT_QPA_PLATFORM` to `offscreen`. CI also runs the full test suite on pushes and pull requests.

