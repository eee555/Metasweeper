"""
openapi_client - spec 驱动通用客户端

运行时读取缓存的 openapi.json（spec dict），按 operationId 动态发现端点：
- 参数按 spec 自动绑定到 path / query / body
- 请求体按 spec 声明的 content-type 自动编码（JSON / form-urlencoded / multipart）
- 响应通过生成的 msgspec.Struct 模型做 msgspec.json.decode
- 统一异常翻译（见 errors.py），429 自动退避重试一次

本模块与具体站点无关：base_url、User-Agent 均由调用方传入。
网络逻辑全部集中在此处；生成的端点门面只是补全友好层，最终都委托给本类。
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote, urlencode

import msgspec

from .errors import (
    ApiClientError,
    AuthError,
    RateLimitError,
    SpecError,
    ValidationError,
)
from .transport import (
    RequestsTransport,
    Transport,
    TransportError,
    TransportResponse,
)

# 请求体 content-type 优先级（同一操作声明多种时取第一个命中的）
_CONTENT_TYPE_PRIORITY = ("application/json", "application/x-www-form-urlencoded", "multipart/form-data")

# 429 退避等待秒数（等待 1.1s 后重试一次）
_RATE_LIMIT_BACKOFF_SEC = 1.1


def build_model_registry(module: Any) -> dict[str, type]:
    """从生成的模型模块构建 名称 -> msgspec.Struct 类 的注册表"""
    registry: dict[str, type] = {}
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, msgspec.Struct):
            registry[name] = obj
    return registry


def _resolve_response_type(schema: dict[str, Any] | None,
                           registry: dict[str, type]) -> Any:
    """把 200 响应的 JSON schema 解析为可用于 msgspec.json.decode(type=...) 的类型

    支持: $ref 模型 / 数组 / 基础类型 / 无内容(None)
    """
    if not schema:
        return None
    if "$ref" in schema:
        model_name = schema["$ref"].rsplit("/", 1)[-1]
        model = registry.get(model_name)
        if model is None:
            raise SpecError(f"响应模型 {model_name} 不在模型注册表中")
        return model
    if schema.get("type") == "array":
        inner = _resolve_response_type(schema.get("items"), registry)
        return list[inner] if inner is not None else list[Any]
    t = schema.get("type")
    if t is None:
        return Any
    return {"string": str, "integer": int, "number": float, "boolean": bool}.get(t, Any)


class SpecDrivenClient:
    """按 openapi spec 驱动的通用 HTTP 客户端（站点无关）"""

    def __init__(
        self,
        spec: dict[str, Any],
        model_registry: dict[str, type],
        base_url: str,
        timeout: float = 10.0,
        user_agent: str = "Metasweeper-Plugin/1.0",
        transport: Transport | None = None,
    ) -> None:
        self._spec = spec
        self._registry = model_registry
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._endpoints: dict[str, tuple[str, str, dict[str, Any]]] = {}
        self._build_endpoint_index()
        # 传输层可注入（如 QtNetworkTransport）；默认走 requests 实现
        self._transport: Transport = transport if transport is not None else RequestsTransport(user_agent)

    @property
    def session(self):
        """向后兼容：默认（requests）传输时暴露底层 session

        注意：注入自定义 transport 后此属性不可用（返回 None）。
        """
        return getattr(self._transport, "session", None)

    # ------------------------------------------------------------------ 索引
    def _build_endpoint_index(self) -> None:
        """遍历 spec paths，建立 operationId -> (method, path, operation) 索引"""
        for path, methods in self._spec.get("paths", {}).items():
            for method, op in methods.items():
                if method not in ("get", "post", "put", "delete", "patch"):
                    continue
                op_id = op.get("operationId")
                if op_id:
                    self._endpoints[op_id] = (method.upper(), path, op)

    # ------------------------------------------------------------------ 认证
    def set_token(self, token: str) -> None:
        """设置认证 token

        TODO(实测): 多数 openapi spec 未声明 securitySchemes，认证方式因站点而异。
        此处先按最常见的 Bearer 头实现，接入具体站点时需实测确认
        （也可能是 Cookie/自定义头，可通过本方法或 transport.set_default_headers 注入）。
        """
        self._transport.set_default_headers({"Authorization": f"Bearer {token}"})

    # ------------------------------------------------------------------ 调用
    def call(self, operation_id: str, **params: Any) -> Any:
        """按 operationId 执行一次 API 调用

        params 的键需与 spec 中参数名一致；body 参数固定用键名 ``body`` 传入。
        返回值已按 200 响应 schema 解码为模型实例 / list[模型] / 基础类型 / None。
        """
        entry = self._endpoints.get(operation_id)
        if entry is None:
            raise SpecError(f"operationId '{operation_id}' 不存在于 openapi spec")
        method, path_template, op = entry

        path_params, query_params, body = self._bind_params(op, params)
        url = self._base_url + self._render_path(path_template, path_params)

        data: dict[str, Any] | None = None
        json_body: Any = None
        files: dict[str, Any] | None = None
        if body is not None:
            content_types = op.get("requestBody", {}).get("content", {})
            ct = next((c for c in _CONTENT_TYPE_PRIORITY if c in content_types), None)
            if ct == "application/json":
                json_body = body
            elif ct == "application/x-www-form-urlencoded":
                data = self._struct_to_flat_dict(body)
            elif ct == "multipart/form-data":
                # requests 用 files={k: (None, v)} 发送 multipart 表单字段
                files = {k: (None, str(v)) for k, v in self._struct_to_flat_dict(body).items()}
            else:
                raise SpecError(f"不支持的请求体 content-type: {list(content_types)}")

        return self._request_with_retry(
            method, url, params=query_params, data=data, json_body=json_body, files=files,
            op=op,
        )

    # -------------------------------------------------------------- 参数绑定
    @staticmethod
    def _bind_params(op: dict[str, Any], params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Any]:
        """把调用方 kwargs 按 spec 分拣为 (path参数, query参数, body)"""
        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        body: Any = params.pop("body", None)

        for prm in op.get("parameters", []):
            name = prm["name"]
            if name not in params:
                continue
            value = params.pop(name)
            where = prm.get("in")
            if where == "path":
                path_params[name] = value
            elif where == "query":
                query_params[name] = value
            # header/cookie 参数首期未用到，忽略

        if params:
            unknown = ", ".join(sorted(params))
            raise SpecError(f"传入了 spec 未声明的参数: {unknown}")
        return path_params, query_params, body

    @staticmethod
    def _render_path(path_template: str, path_params: dict[str, Any]) -> str:
        url = path_template
        for name, value in path_params.items():
            url = url.replace("{" + name + "}", quote(str(value)))
        return url

    @staticmethod
    def _struct_to_flat_dict(body: Any) -> dict[str, Any]:
        """把 msgspec.Struct / dict / 基础类型展平为可编码的扁平 dict"""
        if isinstance(body, msgspec.Struct):
            return {k: v for k, v in msgspec.structs.asdict(body).items() if v is not None}
        if isinstance(body, dict):
            return {k: v for k, v in body.items() if v is not None}
        raise SpecError(f"请求体类型不支持: {type(body).__name__}")

    # -------------------------------------------------------------- 请求执行
    def _request_with_retry(self, method: str, url: str, *, params: dict[str, Any],
                            data: dict[str, Any] | None, json_body: Any,
                            files: dict[str, Any] | None, op: dict[str, Any]) -> Any:
        kwargs: dict[str, Any] = {"timeout": self._timeout}
        if params:
            kwargs["params"] = params
        if data is not None:
            kwargs["data"] = urlencode(data)
            kwargs.setdefault("headers", {})["Content-Type"] = "application/x-www-form-urlencoded"
        if json_body is not None:
            kwargs["data"] = msgspec.json.encode(json_body)
            kwargs.setdefault("headers", {})["Content-Type"] = "application/json"
        if files is not None:
            kwargs["files"] = files

        for attempt in (1, 2):  # 429 时退避后重试一次
            try:
                resp = self._transport.request(
                    method, url,
                    headers=kwargs.get("headers"),
                    params=kwargs.get("params"),
                    data=kwargs.get("data"),
                    files=kwargs.get("files"),
                    timeout=kwargs["timeout"],
                )
            except TransportError as exc:
                raise ApiClientError(f"网络请求失败: {exc}") from exc

            if resp.status_code == 429 and attempt == 1:
                time.sleep(_RATE_LIMIT_BACKOFF_SEC)
                continue
            break

        return self._decode_response(resp, op)

    # -------------------------------------------------------------- 响应解码
    def _decode_response(self, resp: TransportResponse, op: dict[str, Any]) -> Any:
        if resp.status_code in (401, 403):
            raise AuthError("认证失败（可能需要登录）", status_code=resp.status_code,
                            detail=resp.text[:200])
        if resp.status_code == 429:
            raise RateLimitError("触发服务端限流，重试后仍失败", status_code=429)
        if resp.status_code == 422:
            raise ValidationError("请求参数校验失败", status_code=422,
                                  detail=resp.text[:500])
        if resp.status_code >= 400:
            raise ApiClientError("API 请求失败", status_code=resp.status_code,
                                 detail=resp.text[:200])

        content = op.get("responses", {}).get("200", {}).get("content", {})
        if not content:
            return None  # spec 声明无响应体
        schema = next(iter(content.values()), {}).get("schema")
        expected = _resolve_response_type(schema, self._registry)
        try:
            return msgspec.json.decode(resp.content, type=expected)
        except msgspec.ValidationError as exc:
            raise ApiClientError(
                f"响应与模型不匹配: {exc}", status_code=resp.status_code,
                detail=resp.text[:200],
            ) from exc
