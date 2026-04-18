"""AI Provider Service - 统一AI服务层

支持多种AI服务商，提供统一的调用接口。
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# 支持的AI服务商配置
AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "models": [
            "gpt-4o-2024-11-20",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo"
        ],
        "default_model": "gpt-4o-mini",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": [
            "claude-opus-4-20251120",
            "claude-sonnet-4-20251120",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
            "claude-3-sonnet-latest",
            "claude-3-haiku-latest"
        ],
        "default_model": "claude-3-5-sonnet-latest",
        "api_url": "https://api.anthropic.com/v1/messages",
        "supports_streaming": True,
        "requires_strict_format": True
    },
    "zhipu": {
        "name": "智谱AI (GLM)",
        "models": [
            "glm-4-plus",
            "glm-4-flash",
            "glm-4-long",
            "glm-4-alltools",
            "glm-4",
            "glm-3-turbo"
        ],
        "default_model": "glm-4-flash",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False
    },
    "qwen": {
        "name": "阿里云 (Qwen)",
        "models": [
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
            "qwen-max-long上下文"
        ],
        "default_model": "qwen-plus",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "supports_streaming": True,
        "requires_strict_format": False
    },
    "minimax": {
        "name": "MiniMax",
        "models": [
            "MiniMax-M2.7",
            "abab6.5s-chat",
            "abab6-chat"
        ],
        "default_model": "MiniMax-M2.7",
        "api_url": "https://api.minimax.chat/v1/text/chatcompletion_v2",
        "supports_streaming": True,
        "requires_strict_format": False
    },
    "baidu": {
        "name": "百度文心一言",
        "models": [
            "ernie-4.0-8k-latest",
            "ernie-4.0-8k",
            "ernie-4.0-turbo-8k-latest",
            "ernie-3.5-8k-latest",
            "ernie-3.5-8k"
        ],
        "default_model": "ernie-4.0-8k-latest",
        "api_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "supports_streaming": False,
        "requires_strict_format": False
    },
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b"
        ],
        "default_model": "gemini-1.5-flash",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "supports_streaming": True,
        "requires_strict_format": False
    }
}


class AIProvider:
    """统一AI服务提供者"""

    def __init__(self):
        self._config: Dict[str, Any] = {
            "provider": "minimax",
            "api_key": "",
            "api_url": "",
            "model": "MiniMax-M2.7",
            "timeout": 120
        }
        self._load_config_from_env()  # 优先从 .env 加载
        self._load_config_from_settings()  # 再从系统设置覆盖

    def _load_config_from_env(self) -> None:
        """从环境变量加载默认配置（主要用于保持向后兼容）"""
        try:
            from app.config import settings
            # 如果 .env 中有 minimax 配置，设为默认值
            minimax_key = getattr(settings, "minimax_api_key", None)
            if minimax_key and minimax_key not in ("", "your-minimax-api-key"):
                self._config["api_key"] = minimax_key
                self._config["provider"] = "minimax"
                self._config["model"] = "MiniMax-M2.7"
                logger.info("已从 .env 加载 MiniMax API 密钥")
        except Exception as e:
            logger.debug(f"从环境变量加载配置失败: {e}")

    def _load_config_from_settings(self) -> None:
        """从系统设置加载配置（仅当系统设置有效时覆盖 .env 的配置）"""
        try:
            from app.routers.system import MOCK_SETTINGS

            # 只有当系统设置中明确保存了有效的 API 密钥时才覆盖环境变量
            # （不为空且不为掩码 ****）
            saved_api_key = MOCK_SETTINGS.get("ai_api_key", None)
            if saved_api_key and saved_api_key.value and saved_api_key.value != "****":
                self._config["api_key"] = saved_api_key.value
                logger.info(f"已从系统设置加载 AI 配置: provider={self._config['provider']}")

            # 加载其他配置（仅当系统设置中的值有效时才覆盖）
            saved_provider = MOCK_SETTINGS.get("ai_provider", None)
            if saved_provider and saved_provider.value:
                self._config["provider"] = saved_provider.value

            saved_model = MOCK_SETTINGS.get("ai_model", None)
            if saved_model and saved_model.value:
                self._config["model"] = saved_model.value

            saved_api_url = MOCK_SETTINGS.get("ai_api_url", None)
            if saved_api_url and saved_api_url.value:
                self._config["api_url"] = saved_api_url.value

            saved_timeout = MOCK_SETTINGS.get("ai_timeout", None)
            if saved_timeout and saved_timeout.value:
                self._config["timeout"] = saved_timeout.value

        except ImportError:
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
            "timeout": timeout
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
            "supports_streaming": provider_info.get("supports_streaming", False)
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Optional[str]:
        """发送对话请求"""
        provider_key = self._config["provider"]
        api_key = self._config["api_key"]
        api_url = self._config["api_url"]
        model = model or self._config["model"]
        timeout = self._config.get("timeout", 120)

        if not api_key:
            raise ValueError(f"API密钥未配置，请先在系统设置中配置{self.get_provider_info().get('name', provider_key)}的API密钥")

        provider_info = AI_PROVIDERS.get(provider_key, {})

        # 根据不同服务商调用不同的API
        if provider_key == "openai":
            return await self._call_openai(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "anthropic":
            return await self._call_anthropic(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "zhipu":
            return await self._call_zhipu(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "qwen":
            return await self._call_qwen(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "minimax":
            return await self._call_minimax(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "baidu":
            return await self._call_baidu(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        elif provider_key == "gemini":
            return await self._call_gemini(api_key, api_url, model, messages, max_tokens, temperature, timeout)
        else:
            raise ValueError(f"不支持的AI服务商: {provider_key}")

    async def _call_openai(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用OpenAI API"""
        url = api_url or AI_PROVIDERS["openai"]["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                logger.error(f"OpenAI API错误: {response.status_code} - {response.text}")
                return None

    async def _call_anthropic(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用Anthropic Claude API"""
        url = api_url or AI_PROVIDERS["anthropic"]["api_url"]
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        # Anthropic使用不同的消息格式
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                continue  # Anthropic不使用system角色
            anthropic_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("content", [{}])[0].get("text")
            else:
                logger.error(f"Anthropic API错误: {response.status_code} - {response.text}")
                return None

    async def _call_zhipu(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用智谱AI API"""
        url = api_url or AI_PROVIDERS["zhipu"]["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                logger.error(f"智谱AI API错误: {response.status_code} - {response.text}")
                return None

    async def _call_qwen(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用阿里云Qwen API"""
        url = api_url or AI_PROVIDERS["qwen"]["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                logger.error(f"Qwen API错误: {response.status_code} - {response.text}")
                return None

    async def _call_minimax(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用MiniMax API"""
        from app.config import settings
        url = api_url or AI_PROVIDERS["minimax"]["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        # 添加 group_id（如果配置了的话）
        if settings.minimax_group_id:
            payload["group_id"] = settings.minimax_group_id

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                logger.error(f"MiniMax API错误: {response.status_code} - {response.text}")
                return None

    async def _call_baidu(
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用百度文心一言API"""
        # 百度API使用access_token认证，需要先获取
        access_token = await self._get_baidu_access_token(api_key)
        if not access_token:
            return None

        url = f"{api_url or AI_PROVIDERS['baidu']['api_url']}?access_token={access_token}"
        headers = {
            "Content-Type": "application/json"
        }

        # 将消息格式转换为百度的格式
        baidu_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue
            baidu_messages.append({
                "role": "user" if role == "user" else "assistant",
                "content": msg.get("content", "")
            })

        payload = {
            "model": model,
            "messages": baidu_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("result", {}).get("generated_text", "")
            else:
                logger.error(f"百度API错误: {response.status_code} - {response.text}")
                return None

    async def _get_baidu_access_token(self, api_key: str) -> Optional[str]:
        """获取百度API access_token（使用API Key和Secret Key）"""
        # 百度使用 client_id 和 client_secret 获取access_token
        # 这里假设api_key格式为 "client_id:client_secret"
        try:
            parts = api_key.split(":")
            if len(parts) != 2:
                logger.error("百度API密钥格式错误，应为 client_id:client_secret")
                return None

            client_id, client_secret = parts
            token_url = "https://aip.baidubce.com/oauth/2.0/token"

            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret
                })

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
        self, api_key: str, api_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float, timeout: int
    ) -> Optional[str]:
        """调用Google Gemini API"""
        url = f"{(api_url or AI_PROVIDERS['gemini']['api_url'])}/{model}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }

        # 将消息格式转换为Gemini格式
        contents = []
        for msg in messages:
            if msg.get("role") == "system":
                continue
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [{}])
                if candidates:
                    content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return content
                return None
            else:
                logger.error(f"Gemini API错误: {response.status_code} - {response.text}")
                return None

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            result = await self.chat(
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=100,
                temperature=0.7
            )
            if result:
                return {"success": True, "message": "连接成功"}
            else:
                return {"success": False, "message": "连接失败，未收到响应"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}


# 全局单例
_ai_provider: Optional[AIProvider] = None


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
