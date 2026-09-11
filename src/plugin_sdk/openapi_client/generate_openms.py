"""openms API 客户端一键生成脚本

一条命令完成全部代码生成:
    1. 下载/刷新 openapi.json -> openms/openapi.json（缓存基线）
    2. datamodel-code-generator 生成 msgspec.Struct 模型 -> openms/models_gen.py
    3. 生成端点门面 -> openms/api_endpoints.py
    4. 生成薄封装包入口 -> openms/__init__.py（导出 create_client / OpenmsApi / 全部模型类）
    5. 对生成物做 import 自检

运行方式（二选一，项目根或 src 目录下均可）::

    python -m plugin_sdk.openapi_client.generate_openms
    python src/plugin_sdk/openapi_client/generate_openms.py

依赖说明:
    - 运行期: requests + msgspec（已随 plugin_sdk 分发）
    - 生成期: datamodel-code-generator（不进 requirements.txt，缺失时本脚本会给出安装提示）

脚本幂等: 重复运行会覆盖旧生成物。
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- 路径自举
# 本脚本位于 src/plugin_sdk/openapi_client/ 下；无论以模块方式还是直接运行，
# 都把 src 目录加入 sys.path，保证 plugin_sdk 可导入。
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from plugin_sdk.openapi_client.codegen import (  # noqa: E402
    download_spec,
    generate_endpoints_facade,
    run_model_codegen,
)

# ---------------------------------------------------------------- 默认参数
# openms 站点内置参数（如需对接其他站点，复制本脚本改这几行即可）
SPEC_URL = "https://openms.top/api/openapi.json"
DEFAULT_BASE_URL = "https://openms.top"
FACADE_CLASS_NAME = "OpenmsApi"

# 生成物输出目录: src/plugin_sdk/openapi_client/openms/
OUTPUT_DIR = Path(__file__).resolve().parent / "openms"
SPEC_PATH = OUTPUT_DIR / "openapi.json"
MODELS_PATH = OUTPUT_DIR / "models_gen.py"
FACADE_PATH = OUTPUT_DIR / "api_endpoints.py"
INIT_PATH = OUTPUT_DIR / "__init__.py"

# 生成包入口的 docstring 标题
INIT_TITLE = "openms API 客户端（自动生成）"


# ---------------------------------------------------------------- 生成入口
def generate_init(models_path: Path, title: str = INIT_TITLE) -> list[str]:
    """生成 openms/__init__.py 薄封装

    通过导入刚生成的 models_gen 枚举全部 msgspec.Struct 模型类，
    生成显式 import 列表（IDE 补全友好），并导出 create_client 工厂。

    Returns:
        导出的模型类名列表
    """
    # 以 openms 包的父目录（openapi_client）为基准导入 models_gen，
    # 避免依赖 openms 包本身已存在 __init__.py
    module_name = "plugin_sdk.openapi_client.openms.models_gen"
    models_module = importlib.import_module(module_name)

    # 枚举全部 msgspec.Struct 模型类（按名称排序，保证输出稳定）
    model_names = sorted(
        name for name, obj in vars(models_module).items()
        if not name.startswith("_")
        and isinstance(obj, type)
        and obj.__module__ == module_name
        and hasattr(obj, "__struct_fields__")
    )

    models_import = ",\n    ".join(model_names)
    all_lines = "\n".join(f'    "{n}",' for n in model_names)

    src = f'''"""
{title}

自动生成，勿手改。运行生成脚本重新生成:
    python -m plugin_sdk.openapi_client.generate_openms

用法::

    from plugin_sdk.openapi_client.openms import create_client, OpenmsApi

    client = create_client()                # base_url 默认 https://openms.top
    api = OpenmsApi(client)                 # 端点门面（IDE 补全友好）
    result = api.userprofile_get_user_info(user_id=1)   # 返回 msgspec.Struct 模型实例
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugin_sdk.openapi_client.client import SpecDrivenClient, build_model_registry
from plugin_sdk.openapi_client.transport import Transport
from . import models_gen as _models_gen
from .api_endpoints import OpenmsApi
from .models_gen import (
    {models_import},
)

DEFAULT_BASE_URL = "{DEFAULT_BASE_URL}"

# 缓存的 openapi.json（与本包一起分发，运行期只读）
_SPEC_PATH = Path(__file__).resolve().parent / "openapi.json"


def create_client(
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = "Metasweeper-Plugin/1.0",
    transport: Transport | None = None,
) -> SpecDrivenClient:
    """创建已就绪的 openms API 客户端

    内部读取随包分发的 openapi.json 缓存、构建模型注册表。

    Args:
        base_url: 站点地址，默认 https://openms.top，可传参覆盖
        timeout: 请求超时秒数
        user_agent: User-Agent 请求头
        transport: 自定义传输层实现（如 QtNetworkTransport）；默认 requests 传输
    """
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    return SpecDrivenClient(
        spec,
        build_model_registry(_models_gen),
        base_url=base_url,
        timeout=timeout,
        user_agent=user_agent,
        transport=transport,
    )


__all__ = [
    "create_client",
    "OpenmsApi",
{all_lines}
]
'''
    INIT_PATH.write_text(src, encoding="utf-8")
    return model_names


def self_check() -> None:
    """对生成物做 import 自检（子进程，隔离当前进程状态）"""
    code = (
        "from plugin_sdk.openapi_client.openms import create_client, OpenmsApi; "
        "c = create_client(); "
        "assert hasattr(c, 'call') and isinstance(OpenmsApi, type); "
        "print('import self-check ok')"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("生成物 import 自检失败，请检查上方报错信息。")
    print(result.stdout.strip())


def main() -> int:
    print("=" * 60)
    print("openms API 客户端一键生成")
    print("=" * 60)
    print(f"spec URL : {SPEC_URL}")
    print(f"输出目录 : {OUTPUT_DIR}")
    print()

    # 生成期依赖检查: datamodel-code-generator
    if importlib.util.find_spec("datamodel_code_generator") is None:
        print(
            "[错误] 未安装生成期依赖 datamodel-code-generator。\n"
            "       请执行: pip install datamodel-code-generator\n"
            "       （仅生成期需要，不进 requirements.txt）",
            file=sys.stderr,
        )
        return 1

    # 1. 下载/刷新 openapi.json
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[1/5] 下载 spec -> {SPEC_PATH}")
    download_spec(SPEC_URL, SPEC_PATH)
    spec: dict[str, Any] = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    print(f"      paths={len(spec.get('paths', {}))} "
          f"schemas={len(spec.get('components', {}).get('schemas', {}))}")

    # 2. 生成模型文件
    print(f"[2/5] 生成模型 -> {MODELS_PATH}")
    run_model_codegen(SPEC_PATH, MODELS_PATH)

    # 3. 生成端点门面
    print(f"[3/5] 生成端点门面 -> {FACADE_PATH}")
    n_methods = generate_endpoints_facade(
        spec,
        FACADE_PATH,
        facade_class_name=FACADE_CLASS_NAME,
        models_import_module=".models_gen",
        title="openms API 端点门面（自动生成）",
    )
    print(f"      共生成 {n_methods} 个端点方法")

    # 4. 生成包入口 __init__.py
    print(f"[4/5] 生成包入口 -> {INIT_PATH}")
    model_names = generate_init(MODELS_PATH)
    print(f"      导出 {len(model_names)} 个模型类")

    # 5. import 自检
    print("[5/5] 生成物 import 自检")
    self_check()

    print()
    print("生成完成，产物清单:")
    for p in (SPEC_PATH, MODELS_PATH, FACADE_PATH, INIT_PATH):
        print(f"  {p.relative_to(_SRC_DIR)}  ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
