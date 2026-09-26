"""
openapi_client - 传输层抽象

把「怎么发 HTTP」与「怎么编解码/退避/翻译异常」解耦：

- ``Transport``: 传输层协议（typing.Protocol），调用方（SpecDrivenClient）
  只依赖该接口
- ``RequestsTransport``: 基于 requests.Session 的默认实现（行为与改造前
  client.py 内嵌的 session 逻辑完全一致）
- ``QtNetworkTransport``: 基于 PySide6 QNetworkAccessManager 的实现，
    **PySide6 为惰性导入**（类/工厂函数内部才 import），保证无 Qt 环境
  时本模块仍可正常导入

注意：
- QtNetworkTransport 是同步桥（内部 QEventLoop 阻塞等待），对调用方
  仍是同步 API；**仅可在拥有活动 Qt 事件循环（已创建 QCoreApplication
  /QApplication）的线程中使用**，禁止在非 GUI 线程或无 Qt 环境下调用。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class TransportError(Exception):
    """传输层错误（网络层失败：DNS/连接/超时/中断等，无 HTTP 状态码）

    由具体传输实现抛出，上层 SpecDrivenClient 统一翻译为 ApiClientError。
    """


@dataclass
class TransportResponse:
    """传输层的最小响应载体（与具体 HTTP 库解耦）"""

    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        """把响应体按 UTF-8 解码为文本（错误详情/调试用）"""
        return self.content.decode("utf-8", errors="replace")


@runtime_checkable
class Transport(Protocol):
    """传输层协议：一次同步 HTTP 请求

    实现方约定：
    - 网络层失败（无法拿到 HTTP 状态码）时抛出 TransportError
    - 拿到 HTTP 响应（含 4xx/5xx）时正常返回 TransportResponse，
      状态码语义由上层翻译
    """

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> TransportResponse:
        """执行一次同步 HTTP 请求

        Args:
            method: HTTP 方法（GET/POST/...）
            url: 完整 URL（path 已渲染）
            headers: 本次请求的附加头（如 Content-Type），与默认头合并
            params: query 参数
            data: 请求体（str / bytes，编码由调用方完成）
            files: multipart 表单字段（值为 (None, str) 元组，与 requests 约定一致）
            timeout: 超时秒数
        """
        ...  # pragma: no cover

    def set_default_headers(self, headers: dict[str, str]) -> None:
        """注入/覆盖默认请求头（如 User-Agent、Authorization）"""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# requests 实现（默认）
# ---------------------------------------------------------------------------
class RequestsTransport:
    """基于 requests.Session 的传输实现（与改造前 client.py 行为一致）"""

    def __init__(self, user_agent: str = "Metasweeper-Plugin/1.0") -> None:
        import requests  # 局部导入：requests 缺失时仅在实例化时报错

        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def set_default_headers(self, headers: dict[str, str]) -> None:
        """把默认头写入 session.headers（与改造前直接操作 session.headers 等价）"""
        self.session.headers.update(headers)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> TransportResponse:
        kwargs: dict[str, Any] = {}
        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        if data is not None:
            kwargs["data"] = data
        if files is not None:
            kwargs["files"] = files
        if timeout is not None:
            kwargs["timeout"] = timeout
        try:
            resp = self.session.request(method, url, **kwargs)
        except Exception as exc:  # requests.RequestException 及其子类
            # 统一包装为 TransportError，上层翻译为 ApiClientError
            raise TransportError(str(exc)) from exc
        return TransportResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )


# ---------------------------------------------------------------------------
# QtNetwork 实现（惰性导入 PySide6）
# ---------------------------------------------------------------------------
def _require_qt():
    """惰性导入 PySide6 网络相关类（仅在实际使用 Qt 传输时才触发）"""
    try:
        from PySide6.QtCore import QEventLoop, QUrl
        from PySide6.QtNetwork import (
            QNetworkAccessManager,
            QNetworkReply,
            QNetworkRequest,
        )
    except ImportError as exc:
        raise ImportError(
            "QtNetworkTransport 需要 PySide6（含 QtNetwork 模块），"
            "当前环境未安装或不可用"
        ) from exc
    return QEventLoop, QUrl, QNetworkAccessManager, QNetworkReply, QNetworkRequest


class QtNetworkTransport:
    """基于 QNetworkAccessManager 的同步传输实现

    实现要点：
    - QEventLoop + reply.finished 同步桥：request() 阻塞直至完成，
      对调用方仍是同步 API
    - QTimer 单发定时器实现超时（QtNetwork 无原生 timeout），超时后
      abort reply 并抛出 TransportError
    - 网络层失败（拿不到 HTTP 状态码）→ TransportError；
      拿得到 HTTP 状态码（含 4xx/5xx）→ 正常返回 TransportResponse，
      语义翻译交给上层

    线程约束：仅可在拥有活动 Qt 事件循环（已创建 QCoreApplication/QApplication）
    的线程中使用；QNetworkAccessManager 本身即在本类构造线程中使用。
    """

    def __init__(self, user_agent: str = "Metasweeper-Plugin/1.0") -> None:
        # 惰性导入：模块顶层不 import PySide6
        _, _, mgr_cls, _, req_cls = _require_qt()
        self._QNetworkRequest = req_cls  # 保存类引用，request() 中复用
        self._manager = mgr_cls()
        # 默认请求头存 dict，每次 request 合并（Qt 无 session.headers 概念）
        self._default_headers: dict[str, str] = {"User-Agent": user_agent}

    def set_default_headers(self, headers: dict[str, str]) -> None:
        """合并/覆盖默认请求头（如 set_token 注入 Authorization）"""
        self._default_headers.update(headers)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> TransportResponse:
        QEventLoop, QUrl, _mgr_cls, _reply_cls, QNetworkRequest = _require_qt()

        # ---- URL + query ----
        qurl = QUrl(url)
        if params:
            from PySide6.QtCore import QUrlQuery

            query = QUrlQuery(qurl)
            for key, value in params.items():
                query.addQueryItem(str(key), str(value))
            qurl.setQuery(query)

        # ---- 请求头：默认头 + 本次附加头 ----
        merged = dict(self._default_headers)
        if headers:
            merged.update(headers)
        request = QNetworkRequest(qurl)
        for name, value in merged.items():
            request.setRawHeader(name.encode("utf-8"),
                                 str(value).encode("utf-8"))

        # ---- 请求体：str/bytes -> QByteArray；multipart 手工编码 ----
        body: bytes | None = None
        if files is not None:
            body, extra_headers = self._encode_multipart(files)
            merged.setdefault(
                "Content-Type",
                f"multipart/form-data; boundary={extra_headers['boundary']}",
            )
            request.setRawHeader(
                b"Content-Type", merged["Content-Type"].encode("utf-8")
            )
        elif data is not None:
            body = data if isinstance(
                data, bytes) else str(data).encode("utf-8")

        # ---- 发送 + 同步等待 ----
        reply = self._manager.sendCustomRequest(
            request, method.encode("ascii"), body)

        loop = QEventLoop()
        timed_out = False

        def _on_finished() -> None:
            timer.stop()
            loop.quit()

        def _on_timeout() -> None:
            nonlocal timed_out
            timed_out = True
            reply.abort()  # 触发 finished，_on_finished 随后退出事件循环
            loop.quit()

        from PySide6.QtCore import QTimer

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(_on_timeout)
        reply.finished.connect(_on_finished)
        if timeout is not None:
            timer.start(int(timeout * 1000))

        loop.exec()  # 阻塞直至 finished / 超时
        timer.stop()
        reply.deleteLater()

        if timed_out:
            # 超时主动 abort 后必然走到这里（abort 会触发 finished）
            raise TransportError(f"请求超时（{timeout}s）: {url}")

        # ---- 错误 / 状态码映射 ----
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status_code is None:
            # 拿不到 HTTP 状态码 => 纯网络层失败（DNS/连接被拒/超时中断等）。
            # 仅用 errorString() 描述原因，避免不同 Qt 绑定的 API 差异。
            reason = reply.errorString() or "未知网络错误"
            raise TransportError(f"网络请求失败: {reason}")

        # 有状态码（含 4xx/5xx）=> 交给上层翻译，不在传输层判错
        content = bytes(reply.readAll())
        return TransportResponse(status_code=int(status_code), headers={}, content=content)

    @staticmethod
    def _encode_multipart(files: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        """把 {field: (None, str_value)} 形式的 multipart 字段编码为 bytes

        与 requests 的 files={k: (None, v)} 约定一致（仅表单字段，无文件名）。
        """
        import uuid

        boundary = f"----MetasweeperQt{uuid.uuid4().hex}"
        lines: list[bytes] = []
        for name, value in files.items():
            _filename, text = value if isinstance(
                value, tuple) else (None, value)
            lines.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{text}\r\n'.encode(
                    "utf-8")
            )
        lines.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(lines), {"boundary": boundary}


def create_default_transport(user_agent: str = "Metasweeper-Plugin/1.0") -> Transport:
    """创建默认传输实现（requests）"""
    return RequestsTransport(user_agent=user_agent)
