"""
Function注册表 - 装饰器注册 + OpenAI tools格式 + 执行处理
"""
from __future__ import annotations

import inspect
import json
from typing import Dict, Any, Callable, List, Optional, get_type_hints
from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication

_translate = QCoreApplication.translate


@dataclass
class ParameterInfo:
    """参数信息"""
    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None
    enum_values: Optional[List[str]] = None


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    description: str
    parameters: List[ParameterInfo] = field(default_factory=list)
    function: Optional[Callable] = None


class FunctionRegistry:
    """Function注册表 - 装饰器注册、schema生成、执行处理"""

    def __init__(self):
        self.functions: Dict[str, FunctionInfo] = {}

    # ═══════════════════════════════════════════════════════════════
    # 注册相关
    # ═══════════════════════════════════════════════════════════════

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        param_descriptions: Optional[Dict[str, str]] = None
    ):
        """
        装饰器：注册函数供 LLM 调用

        Example:
            @registry.register(
                description="点击格子",
                param_descriptions={"x": "X坐标", "y": "Y坐标"}
            )
            def click_cell(x: int, y: int) -> Dict[str, Any]:
                return {"success": True}
        """
        def decorator(func: Callable) -> Callable:
            func_name = name or func.__name__
            func_description = description or (func.__doc__ or "").strip()

            sig = inspect.signature(func)
            type_hints = get_type_hints(func)

            parameters = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue

                param_type = type_hints.get(param_name, Any)
                type_str = self._get_type_string(param_type)
                param_desc = (param_descriptions or {}).get(param_name, "")
                required = param.default == inspect.Parameter.empty
                default = param.default if param.default != inspect.Parameter.empty else None

                enum_values = None
                if hasattr(param_type, '__members__'):
                    enum_values = list(param_type.__members__.keys())

                parameters.append(ParameterInfo(
                    name=param_name,
                    type=type_str,
                    description=param_desc,
                    required=required,
                    default=default,
                    enum_values=enum_values
                ))

            self.functions[func_name] = FunctionInfo(
                name=func_name,
                description=func_description,
                parameters=parameters,
                function=func
            )
            return func
        return decorator

    def register_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        param_descriptions: Optional[Dict[str, str]] = None
    ) -> None:
        """直接注册函数（非装饰器方式）"""
        decorator = self.register(name, description, param_descriptions)
        decorator(func)

    # ═══════════════════════════════════════════════════════════════
    # Schema 生成
    # ═══════════════════════════════════════════════════════════════

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取 OpenAI tools 格式 schema"""
        schemas = []
        for func_info in self.functions.values():
            properties = {}
            required = []

            for param in func_info.parameters:
                param_schema = {"type": param.type}
                if param.description:
                    param_schema["description"] = param.description
                if param.enum_values:
                    param_schema["enum"] = param.enum_values
                properties[param.name] = param_schema

                if param.required:
                    required.append(param.name)

            tool_schema = {
                "type": "function",
                "function": {
                    "name": func_info.name,
                    "description": func_info.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                    }
                }
            }

            if required:
                tool_schema["function"]["parameters"]["required"] = required

            schemas.append(tool_schema)

        return schemas

    # ═══════════════════════════════════════════════════════════════
    # 执行相关
    # ═══════════════════════════════════════════════════════════════

    def execute_function(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行注册的函数"""
        func_info = self.get_function(name)
        if not func_info or not func_info.function:
            return {"success": False, "error": _translate("Form", "函数 '%1' 未注册").replace("%1", name)}

        try:
            sig = inspect.signature(func_info.function)
            valid_params = {}

            for param_name, param_value in arguments.items():
                if param_name in sig.parameters:
                    # 类型转换
                    param_type = sig.parameters[param_name].annotation
                    if param_type != inspect.Parameter.empty:
                        try:
                            if param_type == int:
                                param_value = int(param_value)
                            elif param_type == float:
                                param_value = float(param_value)
                            elif param_type == bool:
                                param_value = bool(param_value)
                        except (ValueError, TypeError):
                            pass
                    valid_params[param_name] = param_value

            result = func_info.function(**valid_params)

            if isinstance(result, dict):
                if "success" not in result:
                    result["success"] = True
                return result
            else:
                return {"success": True, "result": result}

        except Exception as e:
            return {"success": False, "error": _translate("Form", "函数执行失败: %1").replace("%1", str(e))}

    def handle_tool_calls(self, tool_calls: List[Dict[str, Any]],
                          logger=None, widget=None) -> List[Dict[str, Any]]:
        """
        处理 OpenAI 响应中的 tool_calls，返回工具结果消息列表

        Args:
            tool_calls: OpenAI 响应中的 tool_calls 字段
            logger: 可选的日志记录器
            widget: 可选的 UI 组件（用于显示日志）

        Returns:
            工具结果消息列表，可直接追加到 messages 中
        """
        results = []
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "")
            function_data = tool_call.get("function", {})
            func_name = function_data.get("name", "")

            try:
                func_args_str = function_data.get("arguments", "{}")
                func_args = json.loads(func_args_str) if isinstance(
                    func_args_str, str) else func_args_str
            except json.JSONDecodeError:
                func_args = {}

            if logger:
                logger.info(f"处理 tool call: {func_name}, 参数: {func_args}")
            if widget:
                widget.log_message(_translate("Form", "LLM 调用: %1(%2)").replace(
                    "%1", func_name).replace("%2", str(func_args)))

            # 执行函数
            result = self.execute_function(func_name, func_args)

            if widget:
                if result.get("success"):
                    widget.log_message(_translate(
                        "Form", "执行成功: %1").replace("%1", func_name))
                else:
                    widget.log_message(_translate("Form", "执行失败: %1 - %2").replace(
                        "%1", func_name).replace("%2", result.get('error', _translate("Form", "未知错误"))))

            # 构建工具结果消息
            result_msg = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(result, ensure_ascii=False)
            }
            results.append(result_msg)

        return results

    # ═══════════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════════

    def get_function(self, name: str) -> Optional[FunctionInfo]:
        return self.functions.get(name)

    def get_all_functions(self) -> List[FunctionInfo]:
        return list(self.functions.values())

    def list_function_names(self) -> List[str]:
        return list(self.functions.keys())

    def clear(self) -> None:
        self.functions.clear()

    def remove_function(self, name: str) -> bool:
        if name in self.functions:
            del self.functions[name]
            return True
        return False

    @staticmethod
    def _get_type_string(type_hint) -> str:
        """将类型提示转换为 JSON Schema 类型字符串"""
        if type_hint == int:
            return "integer"
        elif type_hint == float:
            return "number"
        elif type_hint == bool:
            return "boolean"
        elif type_hint == list or (hasattr(type_hint, '__origin__') and type_hint.__origin__ == list):
            return "array"
        elif type_hint == dict or (hasattr(type_hint, '__origin__') and type_hint.__origin__ == dict):
            return "object"
        else:
            return "string"
