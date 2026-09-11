"""
openapi_client - 统一异常层次

所有 OpenAPI 客户端调用异常均继承自 ApiClientError，便于上层统一捕获。
"""
from __future__ import annotations


class ApiClientError(Exception):
    """OpenAPI 客户端异常基类

    属性:
        status_code: HTTP 状态码（网络错误等无状态码场景为 None）
        detail: 服务端返回的错误详情（若有）
    """

    def __init__(self, message: str, status_code: int | None = None,
                 detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code is not None:
            base = f"[HTTP {self.status_code}] {base}"
        return base


class AuthError(ApiClientError):
    """认证/授权失败（401/403，或服务端返回登录态缺失类错误）"""


class RateLimitError(ApiClientError):
    """触发限流（429）。客户端内部会自动退避重试一次，重试仍失败才抛出。"""


class ValidationError(ApiClientError):
    """请求参数校验失败（422）"""


class SpecError(ApiClientError):
    """spec 驱动客户端自身错误：operationId 不存在、参数不匹配、模型缺失等"""
