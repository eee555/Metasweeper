"""Shared Markdown viewer for installed plugins and market details."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPalette, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QLayout, QMessageBox, QTextBrowser, QVBoxLayout

from shared_types.widgets.confirm_dialog import ConfirmDialog

from .icons import action_icon, set_button_box_icons


class _RepositoryReadmeBrowser(QTextBrowser):
    def loadResource(self, resource_type: int, url: QUrl):
        # Online README content can refer to local files and remote resources.
        return None


class _PluginReadmeDialog(ConfirmDialog):
    """插件 README 查看对话框（Markdown 渲染，随系统深浅色自适应）。

    链接点击策略：
    - 内部锚点（目录跳转）→ 滚动到对应标题
    - 本地 .md/.txt 文件 → 用本对话框展示
    - 其他本地文件/目录 → 用系统默认应用打开
    - 外部链接 → 用系统默认浏览器打开
    """

    # 浅色/深色两套配色（与 GitHub 风格接近，保证对比度）
    _LIGHT_BASE = "#ffffff"
    _LIGHT_TEXT = "#24292f"
    _LIGHT_LINK = "#0969da"
    _LIGHT_LINK_VISITED = "#8250df"
    _DARK_BASE = "#0d1117"
    _DARK_TEXT = "#e6edf3"
    _DARK_LINK = "#58a6ff"
    _DARK_LINK_VISITED = "#bc8cff"

    def __init__(self, plugin_name: str, content: str, parent=None,
                 base_dir: Path | None = None, title: str | None = None,
                 *, repository_url: QUrl | None = None):
        self._content = content
        self._base_dir = base_dir or Path.cwd()
        self._repository_url = repository_url
        self._browser: QTextBrowser | None = None
        # 全局 styleHints 单例引用（用于断开 colorSchemeChanged 连接）
        self._style_hints = None
        # 标题 slug → 文档位置，用于目录锚点跳转
        self._heading_positions: dict[str, int] = {}
        if title is None:
            title = (parent.tr("{name} - README").format(name=plugin_name)
                     if parent else f"{plugin_name} - README")
        super().__init__(
            parent=parent,
            title=title,
            buttons=QDialogButtonBox.StandardButton.Close,
        )
        self.setWindowIcon(action_icon("app"))
        set_button_box_icons(self.button_box)
        self.resize(720, 520)
        self._apply_theme()
        self._connect_theme_change()

    def _is_dark(self) -> bool:
        try:
            scheme = QApplication.styleHints().colorScheme()
        except Exception:
            return False
        if scheme == Qt.ColorScheme.Unknown:
            return QApplication.palette().color(QPalette.ColorRole.Base).lightness() < 128
        return scheme == Qt.ColorScheme.Dark

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_theme()

    def _connect_theme_change(self) -> None:
        """监听系统深浅色切换，实时刷新 Markdown 配色。

        ``QApplication.styleHints()`` 是进程级单例，连接必须显式断开，
        否则对话框析构后主题切换会调用已删除的 C++ 对象。
        """
        try:
            hints = QApplication.styleHints()
            hints.colorSchemeChanged.connect(self._apply_theme)
            self._style_hints = hints
            # C++ 对象被销毁时兜底断开（正常路径由 done/closeEvent 处理）
            self.destroyed.connect(self._disconnect_theme_change)
        except Exception:
            self._style_hints = None
            return

    def _disconnect_theme_change(self, *_args) -> None:
        """断开全局 styleHints 信号（幂等，可重复调用）。"""
        hints = getattr(self, "_style_hints", None)
        if hints is None:
            return
        self._style_hints = None
        try:
            hints.colorSchemeChanged.disconnect(self._apply_theme)
        except Exception:
            # 已断开、信号桩缺少 disconnect，或 C++ 对象已销毁
            pass

    def done(self, result: int) -> None:
        """对话框结束（确定/取消/关闭）时断开全局信号。"""
        self._disconnect_theme_change()
        super().done(result)

    def closeEvent(self, event) -> None:
        """关闭时断开全局信号，避免残留连接。"""
        self._disconnect_theme_change()
        super().closeEvent(event)

    def _apply_theme(self, *_args) -> None:
        """按当前深浅色更新文本/链接配色。"""
        if self._browser is None:
            return
        dark = self._is_dark()
        link_color = QColor(self._DARK_LINK if dark else self._LIGHT_LINK)
        palette = self._browser.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(self._DARK_BASE if dark else self._LIGHT_BASE))
        palette.setColor(QPalette.ColorRole.Text, QColor(self._DARK_TEXT if dark else self._LIGHT_TEXT))
        palette.setColor(QPalette.ColorRole.Link, link_color)
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(
            self._DARK_LINK_VISITED if dark else self._LIGHT_LINK_VISITED))
        self._browser.setPalette(palette)

        # Qt's Markdown importer assigns an explicit blue foreground to links.
        document = self._browser.document()
        links = []
        block = document.firstBlock()
        while block.isValid():
            fragments = block.begin()
            while not fragments.atEnd():
                fragment = fragments.fragment()
                if fragment.charFormat().anchorHref():
                    links.append((fragment.position(), fragment.length()))
                fragments += 1
            block = block.next()
        cursor = QTextCursor(document)
        link_format = QTextCharFormat()
        link_format.setForeground(link_color)
        cursor.beginEditBlock()
        for position, length in links:
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(link_format)
        cursor.endEditBlock()

    @staticmethod
    def _heading_slug(text: str) -> str:
        """按 GitHub 规则把标题文本转成锚点 slug。

        小写、空格转连字符、去掉标点（保留中日韩文字、字母、数字、``-``/``_``）。
        Qt 的 Markdown 渲染器不会给标题生成锚点，因此目录里的
        ``#一系统架构概览`` 这类链接需要靠 slug 匹配标题块位置来跳转。
        """
        import unicodedata

        s = text.strip().lower().replace(" ", "-")
        return "".join(
            ch for ch in s
            if ch in "-_" or unicodedata.category(ch)[0] in ("L", "N")
        )

    def _collect_heading_positions(self) -> None:
        """渲染 Markdown 后，记录每个标题块的位置，供目录锚点跳转。"""
        self._heading_positions.clear()
        if self._browser is None:
            return
        block = self._browser.document().firstBlock()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                slug = self._heading_slug(block.text())
                if slug:
                    self._heading_positions.setdefault(slug, block.position())
            block = block.next()

    def _scroll_to_heading(self, fragment: str) -> bool:
        """滚动到 fragment 对应的标题，成功返回 True。"""
        from urllib.parse import unquote

        if self._browser is None:
            return False
        key = unquote(fragment)
        pos = self._heading_positions.get(key)
        if pos is None:
            return False
        cursor = QTextCursor(self._browser.document())
        cursor.setPosition(pos)
        self._browser.setTextCursor(cursor)
        self._browser.ensureCursorVisible()
        return True

    def _resolve_local_path(self, url) -> Path | None:
        """从点击的 URL 解析本地文件路径。

        处理 file:// 绝对路径、相对路径（相对插件目录解析）、
        Windows 盘符路径。非本地文件返回 None。
        """
        from urllib.parse import unquote

        scheme = url.scheme().lower()

        if scheme == "file":
            raw = url.toLocalFile()
            if raw:
                p = Path(raw)
                return p if p.is_absolute() else (self._base_dir / p)

        if scheme in ("", "qt"):
            raw = unquote(url.path())
            if "#" in raw:
                raw = raw.split("#", 1)[0]
            if raw:
                p = Path(raw)
                return p if p.is_absolute() else (self._base_dir / p)

        return None

    def _on_anchor_click(self, url) -> None:
        """处理 README 内链接点击，按文件类型分流。"""
        # 内部锚点（目录跳转）：Qt 不为标题生成锚点，靠标题位置定位滚动
        if not url.path() and url.fragment():
            if self._scroll_to_heading(url.fragment()):
                return
            # 兜底：文档里显式的 HTML <a name="..."> 锚点
            if self._browser:
                self._browser.scrollToAnchor(url.fragment())
            return

        if self._repository_url is not None:
            target = self._repository_url.resolved(url)
            if target.scheme().lower() in {"https", "http"} and target.host():
                QDesktopServices.openUrl(target)
            return

        local_path = self._resolve_local_path(url)

        if local_path is not None:
            if local_path.is_file():
                suffix = local_path.suffix.lower()
                if suffix in (".md", ".txt"):
                    # 用对话框展示
                    try:
                        content = local_path.read_text(
                            encoding="utf-8", errors="replace")
                    except OSError as e:
                        QMessageBox.warning(
                            self, self.tr("README"),
                            self.tr("读取文件失败: {err}").format(err=e))
                        return
                    dlg = _PluginReadmeDialog(
                        local_path.stem, content,
                        parent=self, base_dir=self._base_dir)
                    # 若链接带 #锚点，进入模态循环、布局完成后滚到目标标题
                    fragment = url.fragment()
                    if fragment:
                        QTimer.singleShot(
                            0, lambda d=dlg, f=fragment:
                            d._scroll_to_heading(f))
                    dlg.exec()
                else:
                    # 其他类型文件用系统默认应用打开
                    QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(local_path)))
            elif local_path.is_dir():
                # 目录用系统默认文件管理器打开
                QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(local_path)))
            else:
                # 文件不存在，用原始 URL 尝试打开（可能是外部链接）
                QDesktopServices.openUrl(url)
            return

        # 非本地文件 → 系统默认浏览器/应用
        QDesktopServices.openUrl(url)

    def _set_markdown(self, content: str) -> None:
        if self._browser is None:
            return
        features = QTextDocument.MarkdownFeature.MarkdownDialectGitHub
        if self._repository_url is not None:
            features |= QTextDocument.MarkdownFeature.MarkdownNoHTML
        self._browser.document().setMarkdown(content, features)
        self._collect_heading_positions()
        self._apply_theme()

    def _create_content(self) -> QLayout:
        layout = QVBoxLayout()
        if not self._content and self._repository_url is None:
            label = QLabel(self.tr("该插件目录下未找到 README.md"))
            label.setWordWrap(True)
            layout.addWidget(label)
            return layout

        browser = QTextBrowser() if self._repository_url is None else _RepositoryReadmeBrowser()
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.anchorClicked.connect(self._on_anchor_click)
        self._browser = browser

        font = QFont("Microsoft YaHei", 11)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        browser.setFont(font)

        self._set_markdown(self._content)

        layout.addWidget(browser)
        return layout
