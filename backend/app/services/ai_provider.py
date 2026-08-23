"""AI Provider Service - 统一AI服务层

支持多种AI服务商，提供统一的调用接口。

说明：本文件在工作区版本基础上重建（此前因 git checkout 误恢复为旧提交版，
丢失了 AIResponse/用量统计/扩展厂商等）。重建同时应用：
- P2-2：OpenAI 兼容协议厂商统一走 _call_openai_compatible（收敛重复方法）
- P2-8：默认模型统一 minimax-m3；AI_PROVIDERS 模型/价格为示例配置，需按官方核对
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """统一AI调用返回结果，包含内容和用量统计。"""

    content: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    raw_usage: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    error_message: str | None = None


# 各服务商近似单价（USD per 1M tokens），用于成本估算。
# 注意：以下为示例/估算值，实际接入请按各厂商官方定价更新（评估 P2-8）。
_TOKEN_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    },
    "anthropic": {
        "claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku-latest": {"input": 0.8, "output": 4.0},
    },
    "zhipu": {
        "glm-4-flash": {"input": 0.1, "output": 0.1},
        "glm-4-plus": {"input": 0.5, "output": 0.5},
    },
    "qwen": {
        "qwen-plus": {"input": 0.8, "output": 2.0},
        "qwen-turbo": {"input": 0.3, "output": 0.6},
    },
    "minimax": {
        "minimax-m3": {"input": 0.80, "output": 4.0},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.27, "output": 1.10},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    },
    "moonshot": {
        "moonshot-v1-8k": {"input": 0.12, "output": 0.12},
        "moonshot-v1-32k": {"input": 0.24, "output": 0.24},
    },
    "stepfun": {
        "step-1-8k": {"input": 0.15, "output": 0.4},
    },
    "doubao": {
        "doubao-pro-32k": {"input": 0.8, "output": 2.0},
    },
    "mimo": {
        "mimo-7b": {"input": 0.5, "output": 1.5},
    },
    "grok": {
        "grok-2": {"input": 2.0, "output": 10.0},
        "grok-2-mini": {"input": 0.2, "output": 1.0},
    },
    "gemini": {
        "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    },
    "baidu": {
        "ernie-4.0-8k": {"input": 0.12, "output": 0.12},
    },
}


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """根据厂商和模型估算调用成本（USD）。"""
    pricing = _TOKEN_PRICING.get(provider, {}).get(model)
    if pricing is None:
        # 尝试前缀匹配
        for m, p in _TOKEN_PRICING.get(provider, {}).items():
            if model.startswith(m.split("/")[-1]) or model.startswith(m):
                pricing = p
                break
    if pricing is None:
        return 0.0
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]


def _extract_usage(provider: str, data: dict, model: str) -> Dict[str, int]:
    """从不同厂商的 API 响应中提取 token 用量。"""
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    raw_usage = {}

    if provider == "anthropic":
        raw_usage = data.get("usage", {})
        usage["input_tokens"] = raw_usage.get("input_tokens", 0)
        usage["output_tokens"] = raw_usage.get("output_tokens", 0)
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    elif provider == "gemini":
        raw_usage = data.get("usageMetadata", {})
        usage["input_tokens"] = raw_usage.get("promptTokenCount", 0)
        usage["output_tokens"] = raw_usage.get("candidatesTokenCount", 0)
        usage["total_tokens"] = raw_usage.get("totalTokenCount", usage["input_tokens"] + usage["output_tokens"])
    elif provider == "baidu":
        raw_usage = data.get("usage", {})
        usage["total_tokens"] = raw_usage.get("total_tokens", 0)
    else:
        # OpenAI 兼容格式（openai/zhipu/qwen/minimax/deepseek/moonshot/stepfun/doubao/mimo/grok）
        raw_usage = data.get("usage", {})
        usage["input_tokens"] = raw_usage.get("prompt_tokens", 0)
        usage["output_tokens"] = raw_usage.get("completion_tokens", 0)
        usage["total_tokens"] = raw_usage.get("total_tokens", usage["input_tokens"] + usage["output_tokens"])

    return usage


# 支持的AI服务商配置
# 评估 P2-8 说明：模型 ID 与默认 API URL 为示例配置（部分为估算值），
# 实际接入时请按各厂商官方文档核对模型 ID/价格/端点；UI 可配置覆盖。
AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
        "default_model": "claude-3-5-sonnet-latest",
        "api_url": "https://api.anthropic.com/v1/messages",
        "supports_streaming": True,
        "requires_strict_format": True,
    },
    "zhipu": {
        "name": "智谱AI (GLM)",
        "models": ["glm-4-plus", "glm-4-flash"],
        "default_model": "glm-4-flash",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "qwen": {
        "name": "阿里云 (Qwen)",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "default_model": "qwen-plus",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "minimax": {
        "name": "MiniMax",
        "models": ["minimax-m3"],
        "default_model": "minimax-m3",
        "api_url": "https://api.minimaxi.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "baidu": {
        "name": "百度文心一言",
        "models": ["ernie-4.0-8k", "ernie-3.5-8k"],
        "default_model": "ernie-4.0-8k",
        "api_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "supports_streaming": False,
        "requires_strict_format": False,
    },
    "deepseek": {
        "name": "DeepSeek (深度求索)",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "moonshot": {
        "name": "Moonshot (月之暗面)",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k"],
        "default_model": "moonshot-v1-8k",
        "api_url": "https://api.moonshot.cn/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "stepfun": {
        "name": "阶跃星辰 (StepFun)",
        "models": ["step-1-8k", "step-1-32k"],
        "default_model": "step-1-8k",
        "api_url": "https://api.stepfun.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "doubao": {
        "name": "豆包 (字节跳动)",
        "models": ["doubao-pro-32k"],
        "default_model": "doubao-pro-32k",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "mimo": {
        "name": "MiMo (小米)",
        "models": ["mimo-7b"],
        "default_model": "mimo-7b",
        "api_url": "https://api.xiaomi.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "grok": {
        "name": "Grok (xAI)",
        "models": ["grok-2", "grok-2-mini"],
        "default_model": "grok-2",
        "api_url": "https://api.x.ai/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "default_model": "gemini-1.5-flash",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "supports_streaming": True,
        "requires_strict_format": False,
    },
}


class AIProvider:
    """统一AI服务提供者"""

    def __init__(
        self,
        provider_key: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self._config: Dict[str, Any] = {
            "provider": provider_key or "minimax",
            "api_key": api_key or "",
            "api_url": api_url or "",
            # 评估 P2-8：默认模型统一为 AI_PROVIDERS 中的 minimax-m3（原旧的 MiniMax-M2.7）
            "model": model or "minimax-m3",
            "timeout": timeout or 120,
        }
        # 始终尝试从系统设置加载（当未显式传入 api_key 时）
        if not api_key:
            self._load_config_from_env()
            self._load_config_from_settings()

    def _load_config_from_env(self) -> None:
        """从环境变量加载默认配置（主要用于保持向后兼容）"""
        try:
            from app.config import settings

            # 如果 .env 中有 minimax 配置，设为默认值
            minimax_key = getattr(settings, "minimax_api_key", None)
            if minimax_key and minimax_key not in ("", "your-minimax-api-key"):
                self._config["api_key"] = minimax_key
                self._config["provider"] = "minimax"
                self._config["model"] = "minimax-m3"
                logger.info("已从 .env 加载 MiniMax API 密钥")
        except Exception as e:
            logger.debug(f"从环境变量加载配置失败: {e}")

    def _load_config_from_settings(self) -> None:
        """从系统设置加载配置（读 DB，经 settings_service——MOCK_SETTINGS 已废弃）"""
        try:
            from app.services.settings_service import get_ai_config

            ai_config = get_ai_config()

            saved_api_key = ai_config.get("api_key")
            if saved_api_key and saved_api_key != "****":
                self._config["api_key"] = saved_api_key
                logger.info(f"已从系统设置加载 AI 配置: provider={self._config['provider']}")

            saved_provider = ai_config.get("provider")
            if saved_provider:
                self._config["provider"] = saved_provider

            saved_model = ai_config.get("model")
            if saved_model:
                self._config["model"] = saved_model

            saved_api_url = ai_config.get("api_url")
            if saved_api_url:
                self._config["api_url"] = saved_api_url

            saved_timeout = ai_config.get("timeout")
            if saved_timeout:
                try:
                    self._config["timeout"] = int(saved_timeout)
                except (TypeError, ValueError):
                    pass

        except Exception as e:
            logger.warning(f"加载AI配置失败，使用默认配置: {e}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()

    def set_config(self, provider: str, api_key: str, api_url: str = "", model: str = "", timeout: int = 120) -> None:
        """设置配置"""
        self._config = {
            "provider": provider,
            "api_key": api_key,
            "api_url": api_url,
            "model": model or AI_PROVIDERS.get(provider, {}).get("default_model", ""),
            "timeout": timeout,
        }

    def get_provider_info(self) -> Dict[str, Any]:
        """获取服务商信息"""
        provider_key = self._config["provider"]
        provider_info = AI_PROVIDERS.get(provider_key, {})
        return {
            "key": provider_key,
            "name": provider_info.get("name", provider_key),
            "models": provider_info.get("models", []),
            "default_model": provider_info.get("default_model", ""),
            "supports_streaming": provider_info.get("supports_streaming", False),
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        user_id: int | None = None,
        template_id: int | None = None,
    ) -> AIResponse:
        """发送对话请求，返回包含内容和用量统计的 AIResponse"""
        t0 = time.monotonic()
        provider_key = self._config["provider"]
        api_key = self._config["api_key"]
        api_url = self._config["api_url"]
        model = model or self._config["model"]
        timeout = self._config.get("timeout", 120)

        if not api_key:
            elapsed = (time.monotonic() - t0) * 1000
            return AIResponse(
                content=None,
                duration_ms=elapsed,
                error_message=f"API密钥未配置，请先在系统设置中配置{self.get_provider_info().get('name', provider_key)}的API密钥",
            )

        # 根据不同服务商调用不同的API
        # 评估 P2-2：OpenAI 兼容协议厂商统一走 _call_openai_compatible（收敛重复方法），
        # 仅保留协议特殊的 anthropic/gemini/baidu 专用调用。
        openai_compatible_providers = {
            "openai", "zhipu", "qwen", "minimax", "deepseek",
            "moonshot", "stepfun", "doubao", "mimo", "grok",
        }
        if provider_key in openai_compatible_providers:
            result = await self._call_openai_compatible(
                provider_key, api_key, api_url, model, messages, max_tokens, temperature, timeout
            )
        elif provider_key == "anthropic":
            result = await self._call_anthropic(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "gemini":
            result = await self._call_gemini(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "baidu":
            result = await self._call_baidu(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        else:
            elapsed = (time.monotonic() - t0) * 1000
            return AIResponse(
                content=None,
                duration_ms=elapsed,
                error_message=f"不支持的AI服务商: {provider_key}",
            )

        elapsed = (time.monotonic() - t0) * 1000
        if result is not None and isinstance(result, AIResponse):
            result.duration_ms = elapsed
            # 估算成本
            if result.total_tokens > 0:
                result.raw_usage["_estimated_cost_usd"] = _estimate_cost(
                    provider_key, model, result.input_tokens, result.output_tokens
                )
            return result
        elif result is not None and isinstance(result, str):
            # 兼容尚未迁移的调用方（返回纯文本）
            return AIResponse(content=result, duration_ms=elapsed)
        else:
            return AIResponse(content=None, duration_ms=elapsed, error_message="API返回为空")

    async def _call_openai_compatible(
        self,
        provider: str,
        api_key: str,
        api_url: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> AIResponse:
        """统一的 OpenAI 兼容协议调用（评估 P2-2：收敛重复方法）。

        适用于 openai/zhipu/qwen/minimax/deepseek/moonshot/stepfun/doubao/mimo/grok。
        响应格式与 usage 提取差异由 _extract_usage(provider, ...) 处理。
        """
        url = api_url or AI_PROVIDERS[provider]["api_url"]
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    usage = _extract_usage(provider, data, model)
                    return AIResponse(content=content, **usage, raw_usage=data.get("usage", {}))
                else:
                    logger.error(f"{provider} API错误: {response.status_code} - {response.text}")
                    return AIResponse(error_message=f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:
            logger.error(f"{provider} API异常: {exc}")
            return AIResponse(error_message=str(exc))

    async def _call_anthropic(
        self,
        api_key: str,
        api_url: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> AIResponse:
        """调用Anthropic Claude API"""
        url = api_url or AI_PROVIDERS["anthropic"]["api_url"]
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}

        # Anthropic使用不同的消息格式
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                continue  # Anthropic不使用system角色
            anthropic_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {"model": model, "messages": anthropic_messages, "max_tokens": max_tokens, "temperature": temperature}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("content", [{}])[0].get("text")
                    usage = _extract_usage("anthropic", data, model)
                    return AIResponse(content=content, **usage, raw_usage=data.get("usage", {}))
                else:
                    logger.error(f"Anthropic API错误: {response.status_code} - {response.text}")
                    return AIResponse(error_message=f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:
            logger.error(f"Anthropic API异常: {exc}")
            return AIResponse(error_message=str(exc))

    async def _call_baidu(
        self,
        api_key: str,
        api_url: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> AIResponse:
        """调用百度文心一言API"""
        # 百度API使用access_token认证，需要先获取
        access_token = await self._get_baidu_access_token(api_key)
        if not access_token:
            return AIResponse(error_message="获取百度 access_token 失败")

        url = f"{api_url or AI_PROVIDERS['baidu']['api_url']}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}

        # 将消息格式转换为百度的格式
        baidu_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue
            baidu_messages.append({"role": "user" if role == "user" else "assistant", "content": msg.get("content", "")})

        payload = {
            "model": model,
            "messages": baidu_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("result", {}).get("generated_text", "") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = _extract_usage("baidu", data, model)
                    return AIResponse(content=content, **usage, raw_usage=data.get("usage", {}))
                else:
                    logger.error(f"百度API错误: {response.status_code} - {response.text}")
                    return AIResponse(error_message=f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:
            logger.error(f"百度API异常: {exc}")
            return AIResponse(error_message=str(exc))

    async def _get_baidu_access_token(self, api_key: str) -> str | None:
        """获取百度API access_token（API Key 格式为 client_id:client_secret）"""
        try:
            parts = api_key.split(":")
            if len(parts) != 2:
                logger.error("百度API密钥格式错误，应为 client_id:client_secret")
                return None

            client_id, client_secret = parts
            token_url = "https://aip.baidubce.com/oauth/2.0/token"

            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                response = await client.post(
                    token_url,
                    data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("access_token")
                else:
                    logger.error(f"获取百度access_token失败: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"获取百度access_token异常: {e}")
            return None

    async def _call_gemini(
        self,
        api_key: str,
        api_url: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> AIResponse:
        """调用Google Gemini API"""
        url = f"{(api_url or AI_PROVIDERS['gemini']['api_url'])}/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        # 将消息格式转换为Gemini格式
        contents = []
        for msg in messages:
            if msg.get("role") == "system":
                continue
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        payload = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [{}])
                    content = None
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    usage = _extract_usage("gemini", data, model)
                    return AIResponse(content=content, **usage, raw_usage=data.get("usageMetadata", {}))
                else:
                    logger.error(f"Gemini API错误: {response.status_code} - {response.text}")
                    return AIResponse(error_message=f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:
            logger.error(f"Gemini API异常: {exc}")
            return AIResponse(error_message=str(exc))

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            result = await self.chat(messages=[{"role": "user", "content": "你好"}], max_tokens=100, temperature=0.7)
            if result.content:
                return {"success": True, "message": "连接成功"}
            else:
                return {"success": False, "message": f"连接失败: {result.error_message or '未收到响应'}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {e!s}"}


# 全局单例
_ai_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """获取AI服务提供者单例"""
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = AIProvider()
    return _ai_provider


def reload_ai_provider() -> AIProvider:
    """重新加载AI配置"""
    global _ai_provider
    _ai_provider = AIProvider()
    return _ai_provider
