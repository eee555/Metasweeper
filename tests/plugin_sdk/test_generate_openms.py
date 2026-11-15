from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import plugin_sdk.openapi_client.generate_openms as generator


def test_enum_struct_models_imports_and_sorts_names():
    names = generator._enum_struct_models("plugin_sdk.openapi_client.openms.models_requests")
    assert names == sorted(names)
    assert "TournamentSetTournamentIn" in names


def test_generate_init_exports_models_and_request_models(tmp_path, monkeypatch):
    init_path = tmp_path / "__init__.py"
    monkeypatch.setattr(generator, "INIT_PATH", init_path)
    monkeypatch.setattr(generator, "REQUEST_MODELS_PATH", tmp_path / "models_requests.py")
    generator.REQUEST_MODELS_PATH.write_text("", encoding="utf-8")
    names = generator.generate_init(tmp_path / "models_gen.py", title="test package")
    source = init_path.read_text(encoding="utf-8")
    assert names
    assert "test package" in source
    assert "from .models_gen import" in source
    assert "from .models_requests import" in source
    assert "def create_client(" in source


def test_generate_init_omits_absent_request_model_module(tmp_path, monkeypatch):
    init_path = tmp_path / "__init__.py"
    monkeypatch.setattr(generator, "INIT_PATH", init_path)
    monkeypatch.setattr(generator, "REQUEST_MODELS_PATH", tmp_path / "missing.py")
    names = generator.generate_init(tmp_path / "models_gen.py")
    assert names
    assert "models_requests" not in init_path.read_text(encoding="utf-8")


def test_self_check_success_and_failure(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(generator, "_SRC_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(generator.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="import self-check ok\n", stderr=""))
    generator.self_check()
    args, kwargs = calls[0]
    assert args[0][:2] == [generator.sys.executable, "-c"]
    assert kwargs["env"]["PYTHONPATH"].startswith(str(tmp_path))
    assert "import self-check ok" in capsys.readouterr().out

    monkeypatch.setattr(generator.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="out", stderr="err"))
    with pytest.raises(SystemExit, match="import 自检失败"):
        generator.self_check()
    assert "out" in capsys.readouterr().out


def test_main_stops_when_codegen_dependency_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(generator.importlib.util, "find_spec", lambda _name: None)
    assert generator.main() == 1
    assert "datamodel-code-generator" in capsys.readouterr().err


def test_main_runs_all_generation_steps_with_temporary_outputs(tmp_path, monkeypatch, capsys):
    source_root = tmp_path / "src"
    output = source_root / "plugin_sdk" / "openapi_client" / "openms"
    output.mkdir(parents=True)
    spec_path = output / "openapi.json"
    models_path = output / "models_gen.py"
    request_models_path = output / "models_requests.py"
    facade_path = output / "api_endpoints.py"
    init_path = output / "__init__.py"

    monkeypatch.setattr(generator, "_SRC_DIR", source_root)
    monkeypatch.setattr(generator, "OUTPUT_DIR", output)
    monkeypatch.setattr(generator, "SPEC_PATH", spec_path)
    monkeypatch.setattr(generator, "MODELS_PATH", models_path)
    monkeypatch.setattr(generator, "REQUEST_MODELS_PATH", request_models_path)
    monkeypatch.setattr(generator, "FACADE_PATH", facade_path)
    monkeypatch.setattr(generator, "INIT_PATH", init_path)
    monkeypatch.setattr(generator.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(generator, "download_spec", lambda _url, path: Path(path).write_text(
        json.dumps({"paths": {"/": {}}, "components": {"schemas": {"Item": {}}}}), encoding="utf-8"))
    monkeypatch.setattr(generator, "run_model_codegen", lambda _spec, path: Path(path).write_text("class Item: pass\n", encoding="utf-8"))
    monkeypatch.setattr(generator, "synthesize_request_models", lambda _spec: {"create": "CreateIn"})
    def generate_requests(_spec, _mapping, path):
        Path(path).write_text("class CreateIn: pass\n", encoding="utf-8")
        return 1

    def generate_facade(_spec, path, **_kwargs):
        Path(path).write_text("class Api: pass\n", encoding="utf-8")
        return 1

    def generate_package_init(_path):
        init_path.write_text("# generated\n", encoding="utf-8")
        return ["Item", "CreateIn"]

    monkeypatch.setattr(generator, "generate_request_models_module", generate_requests)
    monkeypatch.setattr(generator, "generate_endpoints_facade", generate_facade)
    monkeypatch.setattr(generator, "generate_init", generate_package_init)
    monkeypatch.setattr(generator, "self_check", lambda: None)

    assert generator.main() == 0
    assert spec_path.exists() and models_path.exists() and request_models_path.exists()
    assert facade_path.exists() and "生成完成" in capsys.readouterr().out
