from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from plugin_sdk.openapi_client import codegen


def test_schema_annotation_converters_and_names():
    assert codegen._schema_to_annotation(None, True) == "Any"
    assert codegen._schema_to_annotation({"$ref": "#/schemas/Item"}, False) == "Item | None"
    assert codegen._schema_to_annotation({"type": "array", "items": {"type": "integer"}}, True) == "list[int]"
    assert codegen._schema_to_annotation({"type": "number"}, True) == "float"
    assert codegen._schema_to_annotation({"type": "unknown"}, True) == "Any"
    assert codegen._inline_schema_to_annotation({"anyOf": [{"type": "string"}, {"type": "null"}]}, True) == "str | None"
    assert codegen._inline_schema_to_annotation({"oneOf": [{"type": "integer"}, {"type": "string"}]}, True) == "int | str"
    assert codegen._inline_schema_to_annotation({"type": "array", "items": {"$ref": "#/Item"}}, False) == "list[Item] | None"
    assert codegen._inline_schema_to_annotation({"type": "null"}, True) == "Any"
    assert codegen._inline_schema_to_annotation(None, False) == "Any | None"
    assert codegen._pascal_case("foo__bar") == "FooBar"
    assert codegen._synthesize_model_name("tournament_api_set_tournament") == "TournamentSetTournamentIn"
    assert codegen._method_name("foo_api_bar") == "foo_bar"
    assert codegen._docstring({"summary": "  Summary\nrest"}, "get", "/x") == "Summary\n\nGET /x"
    assert codegen._docstring({"description": "Only description"}, "post", "/x") == "Only description\n\nPOST /x"
    assert codegen._docstring({}, "delete", "/x") == "\nDELETE /x"
    assert codegen._response_annotation({}) == "None"


def test_synthesize_request_models_skips_non_inline_conflicts_and_bad_fields(capsys):
    spec = {
        "components": {"schemas": {"ExistingIn": {}}},
        "paths": {
            "/valid": {"post": {"operationId": "valid_api_create", "requestBody": {"content": {
                "application/json": {"schema": {"type": "object", "properties": {
                    "required": {"type": "string"}, "optional": {"type": "integer"},
                }, "required": ["required"]}}
            }}}},
            "/ref": {"post": {"operationId": "ref_api_create", "requestBody": {"content": {
                "application/json": {"schema": {"$ref": "#/Existing"}}
            }}}},
            "/collision": {"post": {"operationId": "existing_api", "requestBody": {"content": {
                "application/json": {"schema": {"properties": {"name": {"type": "string"}}}}
            }}}},
            "/bad": {"post": {"operationId": "bad_api_create", "requestBody": {"content": {
                "application/json": {"schema": {"properties": {"class": {"type": "string"}}}}
            }}}},
            "/ignored": {"options": {"operationId": "ignored", "requestBody": {"content": {
                "application/json": {"schema": {"properties": {"a": {}}}}
            }}}},
        },
    }
    mapping = codegen.synthesize_request_models(spec)
    assert mapping == {"valid_api_create": "ValidCreateIn"}
    warning = capsys.readouterr().out
    assert "冲突" in warning and "字段名不合法" in warning


def test_generate_request_models_module_writes_required_then_optional_fields(tmp_path):
    output = tmp_path / "models.py"
    spec = {"paths": {"/": {"post": {"operationId": "item_api_create", "requestBody": {"content": {
        "application/json": {"schema": {"properties": {
            "optional": {"type": "string"}, "count": {"type": "integer"},
        }, "required": ["count"]}}
    }}}}}}
    assert codegen.generate_request_models_module(spec, {"item_api_create": "ItemIn"}, output) == 1
    source = output.read_text(encoding="utf-8")
    assert source.index("count: int") < source.index("optional: str | None = None")
    namespace = {}
    exec(compile(source, str(output), "exec"), namespace)
    assert namespace["ItemIn"](3).count == 3
    assert namespace["ItemIn"](3).optional is None


def test_generate_request_models_module_empty_schema_and_title(tmp_path):
    output = tmp_path / "empty.py"
    assert codegen.generate_request_models_module({}, {"empty": "Empty"}, output, title="Custom") == 1
    assert '"""Custom' in output.read_text(encoding="utf-8")
    namespace = {}
    exec(compile(output.read_text(encoding="utf-8"), str(output), "exec"), namespace)
    assert namespace["Empty"]().__class__.__name__ == "Empty"


def test_generate_endpoints_facade_includes_parameters_models_and_responses(tmp_path, monkeypatch):
    spec = {
        "components": {"schemas": {"Item": {}}},
        "paths": {
            "/items/{item_id}": {"get": {
                "operationId": "items_api_get",
                "summary": "Get an item",
                "parameters": [
                    {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {"name": "token", "in": "header", "schema": {"type": "string"}},
                ],
                "responses": {"200": {"content": {"application/json": {"schema": {
                    "type": "array", "items": {"$ref": "#/components/schemas/Item"},
                }}}}},
            }},
            "/items": {"post": {
                "operationId": "items_api_create",
                "requestBody": {"content": {"application/json": {"schema": {
                    "$ref": "#/components/schemas/Item",
                }}}},
                "responses": {"200": {"content": {"application/json": {"schema": {
                    "$ref": "#/components/schemas/Item",
                }}}}},
            }},
            "/inline": {"post": {
                "operationId": "inline_api_create",
                "requestBody": {"content": {"application/json": {"schema": {"properties": {"x": {"type": "string"}}}}}},
                "responses": {"200": {}},
            }},
        },
    }
    destination = tmp_path / "endpoints.py"
    assert codegen.generate_endpoints_facade(
        spec, destination, facade_class_name="ItemsApi",
        request_models={"inline_api_create": "InlineIn"},
    ) == 3
    source = destination.read_text(encoding="utf-8")
    assert "from .models_gen import Item" in source
    assert "from .models_requests import InlineIn" in source
    assert "def items_get(self, item_id: int, limit: int | None = None) -> list[Item]:" in source
    assert 'self._client.call("items_api_get", item_id=item_id, limit=limit)' in source
    assert "body: InlineIn" in source
    package = ModuleType("test_generated")
    package.__path__ = []
    models = ModuleType("test_generated.models_gen")
    models.Item = type("Item", (), {})
    request_models_module = ModuleType("test_generated.models_requests")
    request_models_module.InlineIn = type("InlineIn", (), {})
    monkeypatch.setitem(sys.modules, "test_generated", package)
    monkeypatch.setitem(sys.modules, "test_generated.models_gen", models)
    monkeypatch.setitem(sys.modules, "test_generated.models_requests", request_models_module)
    namespace = {"__name__": "test_generated.facade", "__package__": "test_generated"}
    class FakeClient:
        def call(self, *args, **kwargs):
            return args, kwargs
    exec(compile(source, str(destination), "exec"), namespace)
    facade = namespace["ItemsApi"](FakeClient())
    assert facade.items_get(2, 4) == (("items_api_get",), {"item_id": 2, "limit": 4})


def test_model_codegen_success_failure_and_postprocess(tmp_path, monkeypatch, capsys):
    output = tmp_path / "models.py"
    output.write_text("x = Annotated[None, Meta(max_length=12, min_length=1)]\n", encoding="utf-8")
    monkeypatch.setattr(codegen.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    codegen.run_model_codegen("spec.json", output)
    assert "max_length" not in output.read_text(encoding="utf-8")

    def failed(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="out", stderr="err")
    monkeypatch.setattr(codegen.subprocess, "run", failed)
    with pytest.raises(SystemExit, match="生成失败"):
        codegen.run_model_codegen("spec.json", output)
    assert "out" in capsys.readouterr().out


def test_download_spec_writes_response_bytes(tmp_path, monkeypatch):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def read(self):
            return b'{"openapi":"3.0.0"}'
    calls = []
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout: calls.append((url, timeout)) or Response())
    target = tmp_path / "openapi.json"
    codegen.download_spec("https://example.test/spec", target, timeout=5)
    assert json.loads(target.read_text(encoding="utf-8")) == {"openapi": "3.0.0"}
    assert calls == [("https://example.test/spec", 5)]
