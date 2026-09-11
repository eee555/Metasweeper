"""
openapi_client - API 代码生成工具（生成期依赖，非运行期依赖）

供各插件的生成脚本调用的通用函数：
- run_model_codegen: 调用 datamodel-code-generator 生成 msgspec.Struct 模型文件
- generate_endpoints_facade: 遍历 spec paths 自动生成端点门面文件
  （带完整类型注解，IDE 补全友好；网络逻辑由 client.SpecDrivenClient 执行）

注意: datamodel-code-generator 是生成期依赖，不加入 requirements.txt。
若未安装请先执行: pip install datamodel-code-generator
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

AUTO_GEN_HEADER = """\
\"\"\"{title}

自动生成，勿手改。运行生成脚本重新生成。
\"\"\"
"""

# JSON schema 基础类型 -> Python 类型注解
_PRIMITIVE_MAP = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


# ------------------------------------------------------------------ 模型生成
def run_model_codegen(spec_path: str | Path, output_path: str | Path) -> None:
    """调用 datamodel-code-generator 生成 msgspec.Struct 模型文件

    Args:
        spec_path: openapi.json 路径
        output_path: 生成的模型文件输出路径（如 api/models_gen.py）

    Raises:
        SystemExit: datamodel-code-generator 未安装或生成失败
    """
    cmd = [
        sys.executable, "-m", "datamodel_code_generator",
        "--input", str(spec_path),
        "--output", str(output_path),
        "--output-model-type", "msgspec.Struct",
        "--openapi-scopes", "schemas",
        "--target-python-version", "3.10",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("datamodel-code-generator 生成失败。"
                         "请确认已安装: pip install datamodel-code-generator")

    _postprocess_models(output_path)


def _postprocess_models(models_path: str | Path) -> None:
    """修正 datamodel-code-generator 对 msgspec 的已知输出缺陷:

    None 类型别名上不能带 max_length 约束（msgspec 校验会报
    "Can only set max_length on a str, bytes, or collection type"），
    故对 Annotated[None, Meta(...max_length...))] 移除 max_length。
    """
    text = Path(models_path).read_text(encoding="utf-8")
    fixed = re.sub(
        r"Annotated\[None, Meta\((?P<inner>[^)]*?)max_length=\d+,\s*",
        r"Annotated[None, Meta(\g<inner>",
        text,
    )
    if fixed != text:
        Path(models_path).write_text(fixed, encoding="utf-8")


# ------------------------------------------------------------- 类型解析工具
def _schema_to_annotation(schema: dict[str, Any] | None, required: bool) -> str:
    """把参数/响应的 JSON schema 转为 Python 类型注解字符串"""
    if schema is None:
        return "Any"
    if "$ref" in schema:
        ann = schema["$ref"].rsplit("/", 1)[-1]
    elif schema.get("type") == "array":
        inner = _schema_to_annotation(schema.get("items"), True)
        ann = f"list[{inner}]"
    else:
        ann = _PRIMITIVE_MAP.get(schema.get("type", ""), "Any")
    if not required:
        ann = f"{ann} | None"
    return ann


def _response_annotation(op: dict[str, Any]) -> str:
    """从 200 响应解析返回类型注解；无响应体返回 None"""
    content = op.get("responses", {}).get("200", {}).get("content", {})
    if not content:
        return "None"
    schema = next(iter(content.values()), {}).get("schema")
    return _schema_to_annotation(schema, True)


def _method_name(operation_id: str) -> str:
    """operationId -> 门面方法名（去掉模块段 _api，保持可读且唯一）"""
    return operation_id.replace("_api", "")


def _docstring(op: dict[str, Any], method: str, path: str) -> str:
    summary = op.get("summary") or op.get("description") or ""
    first_line = summary.strip().splitlines()[0] if summary.strip() else ""
    lines = [first_line] if first_line else []
    lines.append("")
    lines.append(f"{method.upper()} {path}")
    return "\n".join(lines)


# ------------------------------------------------------------- 门面文件生成
def generate_endpoints_facade(
    spec: dict[str, Any],
    output_path: str | Path,
    facade_class_name: str = "Api",
    models_import_module: str = ".models_gen",
    title: str = "端点门面（自动生成）",
) -> int:
    """遍历 spec paths，生成端点门面类（补全友好层）

    Args:
        spec: 已加载的 openapi spec dict
        output_path: 门面文件输出路径（如 api/api_endpoints.py）
        facade_class_name: 生成的门面类名（默认 "Api"）
        models_import_module: 模型模块的导入路径（默认相对导入 ".models_gen"）
        title: 生成文件 docstring 标题

    Returns:
        生成的端点方法数量
    """
    valid_models = set(spec.get("components", {}).get("schemas", {}).keys())

    # 收集所有被引用的模型名，用于 import
    referenced_models: set[str] = set()
    methods_src: list[str] = []

    for path, methods in sorted(spec.get("paths", {}).items()):
        for http_method, op in methods.items():
            if http_method not in ("get", "post", "put", "delete", "patch"):
                continue
            op_id = op.get("operationId")
            if not op_id:
                continue

            # 函数签名参数
            sig_parts: list[str] = []
            call_kwargs: list[str] = []
            for prm in op.get("parameters", []):
                if prm.get("in") not in ("path", "query"):
                    continue
                name = prm["name"]
                required = bool(prm.get("required"))
                ann = _schema_to_annotation(prm.get("schema"), required)
                if required:
                    sig_parts.append(f"{name}: {ann}")
                else:
                    sig_parts.append(f"{name}: {ann} = None")
                call_kwargs.append(f"{name}={name}")

            # 请求体参数（固定命名 body）
            rb = op.get("requestBody", {}).get("content", {})
            if rb:
                body_schema = next(iter(rb.values()), {}).get("schema", {})
                if "$ref" in body_schema:
                    model_name = body_schema["$ref"].rsplit("/", 1)[-1]
                    referenced_models.add(model_name)
                    sig_parts.append(f"body: {model_name}")
                else:
                    sig_parts.append("body: dict[str, Any]")
                call_kwargs.append("body=body")

            ret_ann = _response_annotation(op)
            # 返回类型中的模型名加入 import 集合（仅接受 spec 中真实存在的模型）
            for token in ret_ann.replace("list[", " ").replace("]", " ").split():
                if token in valid_models:
                    referenced_models.add(token)

            mname = _method_name(op_id)
            sig = ", ".join(sig_parts)
            sig_str = f"self, {sig}" if sig else "self"
            methods_src.append(
                f"    def {mname}({sig_str}) -> {ret_ann}:\n"
                f"        \"\"\"{_docstring(op, http_method, path)}\"\"\"\n"
                f"        return self._client.call(\"{op_id}\""
                + (", " + ", ".join(call_kwargs) if call_kwargs else "")
                + ")\n"
            )

    imports = ", ".join(sorted(referenced_models))
    import_line = f"from {models_import_module} import {imports}\n" if imports else ""
    file_src = (
        AUTO_GEN_HEADER.format(title=title)
        + "from __future__ import annotations\n\n"
        + "from typing import Any\n\n"
        + import_line
        + "from plugin_sdk.openapi_client.client import SpecDrivenClient\n\n\n"
        + f"class {facade_class_name}:\n"
        + f"    \"\"\"API 端点门面（补全友好层）\n\n"
        + "    所有方法委托给 SpecDrivenClient 执行实际网络请求。\n"
        + "    \"\"\"\n\n"
        + "    def __init__(self, client: SpecDrivenClient) -> None:\n"
        + "        self._client = client\n\n"
        + "\n\n".join(methods_src)
    )
    Path(output_path).write_text(file_src, encoding="utf-8")
    return len(methods_src)


# ---------------------------------------------------------------------- 下载
def download_spec(spec_url: str, save_path: str | Path, timeout: float = 30.0) -> None:
    """下载 openapi.json 覆盖本地缓存

    Args:
        spec_url: spec 下载地址
        save_path: 本地缓存保存路径
        timeout: 下载超时秒数
    """
    import urllib.request

    with urllib.request.urlopen(spec_url, timeout=timeout) as resp:
        Path(save_path).write_bytes(resp.read())
