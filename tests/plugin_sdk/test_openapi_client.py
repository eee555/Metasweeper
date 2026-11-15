from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import msgspec
import pytest

from plugin_sdk.openapi_client import (
    ApiClientError,
    AuthError,
    RateLimitError,
    RequestsTransport,
    SpecDrivenClient,
    SpecError,
    TransportError,
    TransportResponse,
    ValidationError,
    build_model_registry,
)
from plugin_sdk.openapi_client.client import _resolve_response_type


class Item(msgspec.Struct):
    id: int
    label: str


class RenamedBody(msgspec.Struct):
    field_name: str = msgspec.field(name="field-name")
    omitted: str | None = None


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = []

    def set_default_headers(self, headers):
        self.headers.append(headers)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def response(status=200, body=b""):
    return TransportResponse(status, {}, body)


def spec_for(operation, *, method="get", path="/items/{item_id}"):
    operation = dict(operation)
    operation.setdefault("parameters", [{"name": "item_id", "in": "path"}])
    return {"paths": {path: {method: {"operationId": "item_api_get", **operation}}}}


def test_registry_and_response_schema_resolution():
    registry = build_model_registry(SimpleNamespace(Item=Item, value=1))
    assert registry == {"Item": Item}
    assert _resolve_response_type(None, registry) is None
    assert _resolve_response_type({}, registry) is None
    assert _resolve_response_type({"$ref": "#/components/schemas/Item"}, registry) is Item
    assert _resolve_response_type({"type": "array", "items": {"$ref": "#/Item"}}, registry) == list[Item]
    assert _resolve_response_type({"type": "array"}, registry) == list[Any]
    assert _resolve_response_type({"type": "integer"}, registry) is int
    assert _resolve_response_type({"type": "number"}, registry) is float
    assert _resolve_response_type({"type": "boolean"}, registry) is bool
    assert _resolve_response_type({"type": "string"}, registry) is str
    assert _resolve_response_type({"type": "object"}, registry) is Any
    assert _resolve_response_type({}, {}) is None
    with pytest.raises(SpecError, match="不在模型注册表中"):
        _resolve_response_type({"$ref": "#/Missing"}, registry)


def test_call_binds_path_query_and_decodes_model():
    transport = FakeTransport(response(body=b'{"id":3,"label":"three"}'))
    spec = spec_for({
        "parameters": [
            {"name": "item_id", "in": "path", "required": True},
            {"name": "search", "in": "query"},
            {"name": "ignored", "in": "header"},
        ],
        "responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/Item"}}}}},
    })
    client = SpecDrivenClient(spec, {"Item": Item}, "https://example.test/", transport=transport)
    result = client.call("item_api_get", item_id="a b/ç", search="x", ignored="v")
    assert result == Item(3, "three")
    assert transport.calls == [("GET", "https://example.test/items/a%20b/%C3%A7", {
        "headers": None, "params": {"search": "x"}, "data": None,
        "files": None, "timeout": 10.0,
    })]
    assert client.session is None
    with pytest.raises(SpecError, match="不存在"):
        client.call("missing")
    with pytest.raises(SpecError, match="未声明的参数: z"):
        client.call("item_api_get", z=1)


def test_call_encodes_json_form_and_multipart_bodies():
    operation = {
        "requestBody": {"content": {
            "application/json": {},
            "application/x-www-form-urlencoded": {},
            "multipart/form-data": {},
        }},
        "responses": {"200": {}},
    }
    json_transport = FakeTransport(response())
    SpecDrivenClient(spec_for(operation, method="post"), {}, "http://host", transport=json_transport).call(
        "item_api_get", body={"value": 3},
    )
    call = json_transport.calls[0][2]
    assert call["data"] == b'{"value":3}'
    assert call["headers"] == {"Content-Type": "application/json"}

    form_transport = FakeTransport(response())
    form_spec = spec_for({**operation, "requestBody": {"content": {"application/x-www-form-urlencoded": {}}}}, method="post")
    SpecDrivenClient(form_spec, {}, "http://host", transport=form_transport).call(
        "item_api_get", body=RenamedBody("a b", None),
    )
    call = form_transport.calls[0][2]
    assert call["data"] == "field-name=a+b"
    assert call["headers"] == {"Content-Type": "application/x-www-form-urlencoded"}

    multipart_transport = FakeTransport(response())
    multipart_spec = spec_for({**operation, "requestBody": {"content": {"multipart/form-data": {}}}}, method="post")
    SpecDrivenClient(multipart_spec, {}, "http://host", transport=multipart_transport).call(
        "item_api_get", body={"value": 3, "empty": None},
    )
    assert multipart_transport.calls[0][2]["files"] == {"value": (None, "3")}

    with pytest.raises(SpecError, match="请求体类型不支持"):
        SpecDrivenClient(multipart_spec, {}, "http://host", transport=multipart_transport).call(
            "item_api_get", body="unsupported",
        )


def test_call_rejects_unsupported_body_content_type():
    transport = FakeTransport()
    spec = spec_for({"requestBody": {"content": {"text/plain": {}}}}, method="post")
    client = SpecDrivenClient(spec, {}, "http://host", transport=transport)
    with pytest.raises(SpecError, match="不支持的请求体"):
        client.call("item_api_get", body={"a": 1})


def test_response_status_translation_and_detail_truncation(monkeypatch):
    monkeypatch.setattr("plugin_sdk.openapi_client.client.time.sleep", lambda _: None)
    cases = [
        (401, AuthError, 200), (403, AuthError, 200),
        (429, RateLimitError, None), (422, ValidationError, 500),
        (500, ApiClientError, 200),
    ]
    for status, error_type, detail_limit in cases:
        responses = [response(status, b"x" * 600)]
        if status == 429:
            responses.append(response(status, b"x" * 600))
        transport = FakeTransport(*responses)
        client = SpecDrivenClient(spec_for({}), {}, "http://host", transport=transport)
        with pytest.raises(error_type) as caught:
            client.call("item_api_get")
        assert caught.value.status_code == status
        if detail_limit:
            assert len(caught.value.detail) == detail_limit


def test_rate_limit_retries_once_then_decodes(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("plugin_sdk.openapi_client.client.time.sleep", sleep)
    transport = FakeTransport(response(429), response(body=b'{"id":1,"label":"ok"}'))
    op = {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/Item"}}}}}}
    client = SpecDrivenClient(spec_for(op), {"Item": Item}, "http://host", transport=transport)
    assert client.call("item_api_get", item_id=1) == Item(1, "ok")
    assert len(transport.calls) == 2
    sleep.assert_called_once_with(1.1)

    exhausted = FakeTransport(response(429), response(429))
    client = SpecDrivenClient(spec_for({}), {}, "http://host", transport=exhausted)
    with pytest.raises(RateLimitError):
        client.call("item_api_get", item_id=1)
    assert len(exhausted.calls) == 2


def test_transport_errors_and_invalid_model_response_are_wrapped():
    transport = FakeTransport(TransportError("offline"))
    client = SpecDrivenClient(spec_for({}), {}, "http://host", transport=transport)
    with pytest.raises(ApiClientError, match="offline") as caught:
        client.call("item_api_get", item_id=1)
    assert isinstance(caught.value.__cause__, TransportError)

    invalid = FakeTransport(response(body=b'{"id":"bad","label":"x"}'))
    op = {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/Item"}}}}}}
    client = SpecDrivenClient(spec_for(op), {"Item": Item}, "http://host", transport=invalid)
    with pytest.raises(ApiClientError, match="响应与模型不匹配"):
        client.call("item_api_get", item_id=1)


def test_no_content_and_primitive_array_responses():
    no_content = FakeTransport(response())
    client = SpecDrivenClient(spec_for({}), {}, "http://host", transport=no_content)
    assert client.call("item_api_get", item_id=1) is None

    primitive = FakeTransport(response(body=b"[1,2,3]"))
    op = {"responses": {"200": {"content": {"application/json": {"schema": {
        "type": "array", "items": {"type": "integer"},
    }}}}}}
    client = SpecDrivenClient(spec_for(op), {}, "http://host", transport=primitive)
    assert client.call("item_api_get", item_id=1) == [1, 2, 3]


def test_default_transport_session_and_auth_header():
    transport = FakeTransport(response())
    client = SpecDrivenClient(spec_for({}), {}, "http://host", transport=transport)
    client.set_token("secret")
    assert transport.headers == [{"Authorization": "Bearer secret"}]
    assert isinstance(RequestsTransport(), RequestsTransport)
    err = ApiClientError("failure", status_code=400, detail="bad")
    assert str(err) == "[HTTP 400] failure"
    assert err.detail == "bad"


def test_generated_openms_client_exports_models_and_invokes_facade():
    import plugin_sdk
    from plugin_sdk.openapi_client import OpenmsApi, create_client
    from plugin_sdk.openapi_client.openms import UserProfile

    assert plugin_sdk.SpecDrivenClient is SpecDrivenClient
    assert plugin_sdk.OpenmsApi is OpenmsApi
    transport = FakeTransport(response(body=b'{"username":"tester","last_change_avatar":"","last_change_signature":"","id":7}'))
    client = create_client(base_url="https://example.test", transport=transport)
    result = OpenmsApi(client).userprofile_get_user_info(user_id=7)
    assert isinstance(result, UserProfile)
    assert result.id == 7
    assert result.username == "tester"
    assert len(client._registry) > 20
    assert transport.calls[0][0] == "GET"
    assert transport.calls[0][1] == "https://example.test/api/userprofile/info/7"


def test_openapi_lazy_exports_reject_unknown_names():
    import plugin_sdk.openapi_client as package

    with pytest.raises(AttributeError):
        getattr(package, "not_a_public_export")
    with pytest.raises(AttributeError):
        getattr(__import__("plugin_sdk"), "not_a_public_export")


def test_generated_openms_facade_delegates_every_endpoint_method():
    import inspect
    from plugin_sdk.openapi_client.openms import OpenmsApi

    class RecordingClient:
        def __init__(self):
            self.calls = []

        def call(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return args[0]

    client = RecordingClient()
    api = OpenmsApi(client)
    methods = [
        getattr(api, name)
        for name in dir(api)
        if not name.startswith("_") and callable(getattr(api, name))
    ]
    for method in methods:
        signature = inspect.signature(method)
        values = {
            name: None
            for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        }
        method(**values)
    assert len(client.calls) == len(methods) > 40
