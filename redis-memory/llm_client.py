"""LLM Client — Three direct API endpoints using OpenAI-compatible SDK.

Uses openai.OpenAI() for robust HTTP handling (retry, timeout, streaming).
All three APIs are OpenAI-compatible:
- Executor: opencode.ai Zen API (deepseek-v4-flash)
- Reviewer: Volcengine ark API (glm-5.2)
- Pro: api.deepseek.com (deepseek-v4-pro)

Manual retry with exponential backoff handles rate limits and transient failures.
"""

import os
import time
from typing import Optional

from openai import (
    OpenAI,
    DefaultHttpxClient,
    RateLimitError,
    APITimeoutError,
    APIStatusError,
    APIConnectionError,
)

ZEN_BASE = "https://opencode.ai/zen/go/v1"
ZEN_API_KEY = os.environ.get("ZEN_API_KEY", "")

ARK_BASE = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_API_KEY = os.environ.get("ARK_API_KEY", "")

PRO_BASE = "https://api.deepseek.com/v1"
PRO_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def _make_client(base_url: str, api_key: str) -> OpenAI:
    """Create an OpenAI-compatible client with proxy awareness."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    http_client = None
    if proxy:
        try:
            import httpx
            http_client = DefaultHttpxClient(proxy=proxy)
        except Exception:
            pass
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
        max_retries=2,
        timeout=60.0,
    )


RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError)
BACKOFF_DELAYS = [1, 2, 4]


class LLMClient:
    """LLM API client backed by openai.OpenAI() with exponential backoff retry."""

    def __init__(self, base_url: str = ZEN_BASE, api_key: str = "",
                 model: str = "deepseek-v4-flash", manual_retries: int = 2):
        self.model = model
        self._client = _make_client(base_url, api_key)
        self._manual_retries = manual_retries
        self.total_tokens = 0
        self.total_cost = 0.0

    def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        last_error = None
        for attempt in range(self._manual_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                usage = resp.usage
                if usage:
                    self.total_tokens += usage.total_tokens or 0
                    pt = usage.prompt_tokens or 0
                    ct = usage.completion_tokens or 0
                    self.total_cost += (pt * 0.000002) + (ct * 0.00001)

                content = resp.choices[0].message.content or ""
                return content.strip()
            except RETRYABLE as e:
                last_error = e
                if attempt < self._manual_retries:
                    delay = BACKOFF_DELAYS[attempt]
                    time.sleep(delay)
                continue
            except Exception as e:
                return f"[LLM error: {e}]"

        return f"[LLM error: {last_error}]"

    def summarize(self, text: str, template: str = "") -> str:
        system = "You are a concise summarizer. Extract key facts."
        if template:
            system += f"\n\nFormat:\n{template}"
        return self.complete([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Summarize:\n\n{text[:200000]}"},
        ], max_tokens=1000, temperature=0.2)

    def reset_stats(self):
        self.total_tokens = 0
        self.total_cost = 0.0


class DualLLM:
    """Three-model LLM manager.

    Role        | Base URL                                    | Model
    ------------|---------------------------------------------|------------------
    executor    | opencode.ai/zen/go/v1                       | deepseek-v4-flash
    reviewer    | volces.com/api/coding/v1                    | glm-5.2
    pro         | api.deepseek.com/v1                         | deepseek-v4-pro
    """

    def __init__(self):
        self.executor = LLMClient(
            base_url=ZEN_BASE, api_key=ZEN_API_KEY, model="deepseek-v4-flash",
        )
        self.reviewer = LLMClient(
            base_url=ARK_BASE, api_key=ARK_API_KEY, model="glm-5.2",
        )
        self.pro = LLMClient(
            base_url=PRO_BASE, api_key=PRO_API_KEY, model="deepseek-v4-pro",
        )

    def execute(self, messages, max_tokens=4096, temperature=0.3) -> str:
        return self.executor.complete(messages, max_tokens, temperature)

    def review(self, messages, max_tokens=2048, temperature=0.2) -> str:
        return self.reviewer.complete(messages, max_tokens, temperature)

    def deep_audit(self, messages, max_tokens=4096, temperature=0.1) -> str:
        return self.pro.complete(messages, max_tokens, temperature)
