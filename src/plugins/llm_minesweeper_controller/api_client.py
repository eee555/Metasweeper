"""
OpenAI兼容的大模型API客户端 - 使用requests + tools格式function calling
"""
from __future__ import annotations

import json
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication

_translate = QCoreApplication.translate


@dataclass
class ChatResponse:
    """聊天响应数据类"""
    success: bool
    status_code: int = 0
    raw_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # 解析后的内容
    content: Optional[str] = None  # 文本内容
    tool_calls: Optional[List[Dict[str, Any]]] = None  # tool_calls 列表
    finish_reason: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        """是否有 tool_calls"""
        return bool(self.tool_calls)

    @property
    def has_content(self) -> bool:
        """是否有文本内容"""
        return bool(self.content)


class LLMClient:
    """OpenAI兼容的大模型客户端"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> ChatResponse:
        """
        发送聊天请求 (OpenAI /v1/chat/completions)

        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant/system/tool", "content": "..."}]
            tools: OpenAI tools格式的函数定义列表
            temperature: 温度参数
            max_tokens: 最大token数
            reasoning_effort: 深度思考强度 ("low"/"medium"/"high")，None表示关闭

        Returns:
            ChatResponse
        """
        url = f"{self.base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return self._request("POST", url, payload)

    def test_connection(self) -> ChatResponse:
        """测试API连接"""
        messages = [{"role": "user", "content": "Hi, reply with OK."}]
        return self.chat(messages=messages, max_tokens=10)

    def _request(self, method: str, url: str, payload: Dict[str, Any]) -> ChatResponse:
        """执行HTTP请求并解析响应"""
        try:
            response = self.session.request(
                method, url, json=payload, timeout=self.timeout
            )

            response_data = None
            if response.content:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {"raw_response": response.text}

            if response.status_code >= 400:
                error_msg = ""
                if response_data and "error" in response_data:
                    error_msg = response_data["error"].get("message", "")
                return ChatResponse(
                    success=False,
                    status_code=response.status_code,
                    raw_data=response_data,
                    error=error_msg or f"HTTP {response.status_code}",
                )

            # 解析成功响应
            return self._parse_success_response(response_data)

        except requests.exceptions.Timeout:
            return ChatResponse(success=False, error=_translate("Form", "请求超时 (%1秒)").replace("%1", str(self.timeout)))
        except requests.exceptions.ConnectionError:
            return ChatResponse(success=False, error=_translate("Form", "连接失败，请检查网络和API地址"))
        except requests.exceptions.RequestException as e:
            return ChatResponse(success=False, error=_translate("Form", "请求异常: %1").replace("%1", str(e)))
        except Exception as e:
            return ChatResponse(success=False, error=_translate("Form", "未知错误: %1").replace("%1", str(e)))

    def _parse_success_response(self, response_data: Dict[str, Any]) -> ChatResponse:
        """解析成功的API响应"""
        try:
            choice = response_data.get("choices", [{}])[0]
            message = choice.get("message", {})

            # 提取文本内容
            content = message.get("content")

            # 提取 tool_calls
            tool_calls = message.get("tool_calls")

            # 提取 finish_reason
            finish_reason = choice.get("finish_reason")

            # 打印思考内容（如果存在）
            thinking = message.get("thinking") or message.get("reasoning")

            return ChatResponse(
                success=True,
                status_code=200,
                raw_data=response_data,
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )
        except Exception as e:
            return ChatResponse(
                success=True,
                status_code=200,
                raw_data=response_data,
                error=_translate("Form", "解析响应失败: %1").replace("%1", str(e)),
            )

    @staticmethod
    def build_tool_result_message(tool_call_id: str, result: Any) -> Dict[str, Any]:
        """
        构建 tool 结果消息

        Args:
            tool_call_id: tool_call 的 ID
            result: 函数执行结果（会被 JSON 序列化）

        Returns:
            可直接追加到 messages 的消息字典
        """
        if isinstance(result, str):
            content = result
        else:
            content = json.dumps(result, ensure_ascii=False)

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    @staticmethod
    def build_assistant_tool_message(
        content: Optional[str],
        tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        构建 assistant 的 tool_calls 消息（用于多轮对话时保存历史）

        Args:
            content: 文本内容（可能为 None）
            tool_calls: tool_calls 列表

        Returns:
            可追加到 messages 的消息字典
        """
        msg = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
