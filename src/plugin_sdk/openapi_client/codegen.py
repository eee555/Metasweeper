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
import keyword
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


def _inline_schema_to_annotation(schema: dict[str, Any] | None, required: bool) -> str:
    """把内联请求体字段的 JSON schema 转为 Python 类型注解字符串

    相比 _schema_to_annotation 额外支持 anyOf/oneOf 组合
    （如 anyOf[{string,date-time}, {null}] -> str | None），
    这是 FastAPI 风格可选字段的常见写法。
    """
    ann, nullable = _inline_base_annotation(schema)
    if (not required or nullable) and ann != "None":
        ann = f"{ann} | None"
    return ann


def _inline_base_annotation(schema: dict[str, Any] | None) -> tuple[str, bool]:
    """解析内联字段 schema 的基础注解，返回 (注解, 是否可空)"""
    if schema is None:
        return "Any", False
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1], False
    if "anyOf" in schema or "oneOf" in schema:
        branches = schema.get("anyOf") or schema.get("oneOf") or []
        non_null = [b for b in branches if b.get("type") != "null"]
        has_null = len(non_null) != len(branches)
        parts = [_inline_base_annotation(b)[0] for b in non_null]
        if not parts:
            return "None", False
        ann = parts[0] if len(parts) == 1 else " | ".join(parts)
        return ann, has_null
    if schema.get("type") == "array":
        inner, _ = _inline_base_annotation(schema.get("items"))
        return f"list[{inner}]", False
    return _PRIMITIVE_MAP.get(schema.get("type", ""), "Any"), False


def _pascal_case(snake: str) -> str:
    """snake_case -> PascalCase（用于合成请求模型命名）"""
    return "".join(part.capitalize() for part in snake.split("_") if part)


def _synthesize_model_name(operation_id: str) -> str:
    """operationId -> 合成请求模型名

    规则：复用门面方法名（去掉 _api 段）做 PascalCase，再追加 In 后缀。
    如 tournament_api_set_tournament -> TournamentSetTournamentIn。
    """
    return _pascal_case(_method_name(operation_id)) + "In"


def synthesize_request_models(spec: dict[str, Any]) -> dict[str, str]:
    """扫描 spec 全部 paths，为内联 requestBody schema 合成命名请求模型

    datamodel-code-generator 只为 $ref 指向的命名模型生成 Struct，
    内联（properties 直接挂在 requestBody schema 上）的请求体会回退成
    dict[str, Any]。本函数为这类端点按 operationId 合成命名模型，
    返回 operationId -> 模型名 的映射（仅含合成成功的端点）。

    命名冲突（与 components/schemas 或其他合成名重复）或字段名不是
    合法 Python 标识符的端点会被跳过（门面回退 dict）并打印警告。
    """
    existing = set(spec.get("components", {}).get("schemas", {}).keys())
    used: set[str] = set(existing)
    mapping: dict[str, str] = {}

    for path, methods in sorted(spec.get("paths", {}).items()):
        for http_method, op in methods.items():
            if http_method not in ("get", "post", "put", "delete", "patch"):
                continue
            op_id = op.get("operationId")
            if not op_id:
                continue
            content = op.get("requestBody", {}).get("content", {})
            body_schema = next(iter(content.values()), {}).get("schema", {})
            # 仅处理内联 object（有 properties 且无 $ref）
            if "$ref" in body_schema or "properties" not in body_schema:
                continue

            model_name = _synthesize_model_name(op_id)
            if model_name in used:
                print(f"[警告] 合成请求模型名 {model_name}（{op_id}）与既有模型冲突，"
                      f"该端点 body 回退 dict[str, Any]")
                continue
            # 字段名必须可直接作为 Python 属性名（合法标识符且非关键字），
            # 否则 msgspec rename 后 asdict/form 编码的键名映射会引入额外复杂度
            bad_fields = [
                n for n in body_schema["properties"]
                if not n.isidentifier() or keyword.iskeyword(n)
            ]
            if bad_fields:
                print(f"[警告] {op_id} 请求体字段名不合法: {bad_fields}，"
                      f"该端点 body 回退 dict[str, Any]")
                continue

            used.add(model_name)
            mapping[op_id] = model_name
    return mapping


def generate_request_models_module(
    spec: dict[str, Any],
    request_models: dict[str, str],
    output_path: str | Path,
    title: str = "合成请求模型（自动生成）",
) -> int:
    """根据 synthesize_request_models 的映射生成请求模型模块

    用 msgspec.Struct 手写代码生成方式（不经过 datamodel-code-generator），
    字段类型映射复用 _inline_schema_to_annotation：
    - required 字段无默认值，optional 字段默认 None
    - required 字段排在 optional 之前（msgspec 要求无默认值字段在前）

    Returns:
        生成的模型类数量
    """
    # 反查 operationId -> 内联 schema
    op_schemas: dict[str, dict[str, Any]] = {}
    for path, methods in spec.get("paths", {}).items():
        for http_method, op in methods.items():
            op_id = op.get("operationId")
            if op_id in request_models:
                content = op.get("requestBody", {}).get("content", {})
                op_schemas[op_id] = next(iter(content.values()), {}).get("schema", {})

    classes_src: list[str] = []
    for op_id in sorted(request_models):
        model_name = request_models[op_id]
        schema = op_schemas.get(op_id, {})
        properties: dict[str, Any] = schema.get("properties", {})
        required: set[str] = set(schema.get("required", []))
        # required 字段在前（msgspec.Struct 无默认值字段必须排在有默认值字段之前）
        ordered = [n for n in properties if n in required] + \
                  [n for n in properties if n not in required]
        field_lines: list[str] = []
        for name in ordered:
            ann = _inline_schema_to_annotation(properties[name], name in required)
            if name in required:
                field_lines.append(f"    {name}: {ann}")
            else:
                field_lines.append(f"    {name}: {ann} = None")
        body = "\n".join(field_lines) if field_lines else "    pass"
        classes_src.append(f"class {model_name}(Struct):\n{body}\n")

    file_src = (
        AUTO_GEN_HEADER.format(title=title)
        + "from __future__ import annotations\n\n"
        + "from msgspec import Struct\n\n\n"
        + "\n\n".join(classes_src)
    )
    Path(output_path).write_text(file_src, encoding="utf-8")
    return len(request_models)


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
    request_models: dict[str, str] | None = None,
    request_models_import_module: str = ".models_requests",
    title: str = "端点门面（自动生成）",
) -> int:
    """遍历 spec paths，生成端点门面类（补全友好层）

    Args:
        spec: 已加载的 openapi spec dict
        output_path: 门面文件输出路径（如 api/api_endpoints.py）
        facade_class_name: 生成的门面类名（默认 "Api"）
        models_import_module: 模型模块的导入路径（默认相对导入 ".models_gen"）
        request_models: operationId -> 合成请求模型名 的映射（见
            synthesize_request_models）；命中的端点 body 参数使用合成模型注解
        request_models_import_module: 合成请求模型所在模块的导入路径
        title: 生成文件 docstring 标题

    Returns:
        生成的端点方法数量
    """
    request_models = request_models or {}
    valid_models = set(spec.get("components", {}).get("schemas", {}).keys())

    # 收集所有被引用的模型名，用于 import（区分命名模型/合成请求模型两个模块）
    referenced_models: set[str] = set()
    referenced_request_models: set[str] = set()
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
                if op_id in request_models:
                    # 内联 schema 已合成命名请求模型，body 类型化
                    model_name = request_models[op_id]
                    referenced_request_models.add(model_name)
                    sig_parts.append(f"body: {model_name}")
                elif "$ref" in body_schema:
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
    req_imports = ", ".join(sorted(referenced_request_models))
    req_import_line = (
        f"from {request_models_import_module} import {req_imports}\n"
        if req_imports else ""
    )
    file_src = (
        AUTO_GEN_HEADER.format(title=title)
        + "from __future__ import annotations\n\n"
        + "from typing import Any\n\n"
        + import_line
        + req_import_line
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
