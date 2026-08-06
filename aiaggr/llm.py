from __future__ import annotations

import json
import re

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

SYSTEM = "你是资深中文媒体编辑，严格输出 JSON，不要解释。"


class LLMError(RuntimeError):
    pass


def is_mock(settings: dict) -> bool:
    return bool(settings.get("mock", False))


def _require(settings: dict, name: str) -> str:
    val = settings.get(name)
    if not val:
        raise LLMError(
            f"Missing LLM {name}. Set {name} in .env "
            f"(LLM_API_KEY / LLM_BASE_URL / LLM_MODEL) or run with --mock-llm."
        )
    return val


def get_client(settings: dict) -> OpenAI:
    return OpenAI(
        api_key=_require(settings, "api_key"),
        base_url=_require(settings, "base_url"),
        timeout=int(settings.get("timeout", 60)),
        max_retries=0,  # 重试统一交给 tenacity
    )


def _extract_json(text: str) -> str:
    """兼容 markdown code fence 包裹的 JSON。"""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\{\[][\s\S]*[\}\]\s])\s*```", text)
    return match.group(1) if match else text


# 瞬时类错误才重试：超时 / 连接失败 / 限流(429) 退避后可自愈；4xx 业务错误、解析错误不重试
_TRANSIENT = (APITimeoutError, APIConnectionError, RateLimitError)


def _retrier(max_retries: int):
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_random_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type(_TRANSIENT),
    )


def _json_call(system: str, user: str, settings: dict, temperature: float) -> dict | list:
    client = get_client(settings)
    model = _require(settings, "model")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
    except Exception as err:
        reason = str(err).lower()
        if "response_format" in reason or "json_object" in reason or "json mode" in reason:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature
            )
        else:
            raise
    content = response.choices[0].message.content
    return json.loads(_extract_json(content))


def _text_call(system: str, user: str, settings: dict, temperature: float) -> str:
    client = get_client(settings)
    model = _require(settings, "model")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def call_json(
    system: str,
    user: str,
    settings: dict,
    temperature: float | None = None,
) -> dict | list:
    """调用 LLM 并解析 JSON 输出。指数退避重试；mock 模式返回空 dict。"""
    if is_mock(settings):
        return {}
    temp = float(settings.get("temperature", 0.55)) if temperature is None else float(temperature)
    max_retries = max(1, int(settings.get("max_retries", 4)))
    return _retrier(max_retries)(_json_call)(system, user, settings, temp)


def call_text(
    system: str,
    user: str,
    settings: dict,
    temperature: float | None = None,
) -> str:
    """调用 LLM 返回纯文本；mock 模式返回空字符串。"""
    if is_mock(settings):
        return ""
    temp = float(settings.get("temperature", 0.55)) if temperature is None else float(temperature)
    max_retries = max(1, int(settings.get("max_retries", 4)))
    return _retrier(max_retries)(_text_call)(system, user, settings, temp)