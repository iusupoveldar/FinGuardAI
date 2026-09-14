"""Small, dependency-free DeepSeek Chat Completions client."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DeepSeekError(RuntimeError):
    """Base error safe for orchestration-level categorization."""


class DeepSeekBudgetUnavailable(DeepSeekError):
    """The call is disabled, has no key, or provider credit is unavailable."""


class DeepSeekResponseError(DeepSeekError):
    """The provider returned a permanent or malformed response."""


@dataclass(frozen=True)
class DeepSeekResult:
    content: str
    usage: dict[str, int]
    latency_ms: int
    retry_count: int
    provider_model: str


Transport = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


def _http_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> dict[str, Any]:
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured API URL
        return json.loads(response.read().decode("utf-8"))


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 20,
        max_output_tokens: int = 900,
        retries: int = 1,
        transport: Transport = _http_transport,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.retries = max(0, retries)
        self.transport = transport

    def generate(self, messages: list[dict[str, str]]) -> DeepSeekResult:
        if not self.api_key:
            raise DeepSeekBudgetUnavailable("DeepSeek API key is unavailable")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_output_tokens,
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        for attempt in range(self.retries + 1):
            try:
                response = self.transport(
                    f"{self.base_url}/chat/completions",
                    headers,
                    body,
                    self.timeout_seconds,
                )
                choices = response.get("choices") or []
                content = choices[0]["message"]["content"] if choices else None
                if not isinstance(content, str) or not content.strip():
                    raise DeepSeekResponseError("DeepSeek returned empty content")
                raw_usage = response.get("usage") or {}
                prompt_tokens = int(raw_usage.get("prompt_tokens", 0) or 0)
                cache_hits = int(raw_usage.get("prompt_cache_hit_tokens", 0) or 0)
                cache_misses = int(
                    raw_usage.get(
                        "prompt_cache_miss_tokens",
                        max(0, prompt_tokens - cache_hits),
                    )
                    or 0
                )
                completion_tokens = int(raw_usage.get("completion_tokens", 0) or 0)
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "prompt_cache_hit_tokens": cache_hits,
                    "prompt_cache_miss_tokens": cache_misses,
                    "completion_tokens": completion_tokens,
                    "total_tokens": int(
                        raw_usage.get(
                            "total_tokens", prompt_tokens + completion_tokens
                        )
                        or 0
                    ),
                }
                return DeepSeekResult(
                    content=content,
                    usage=usage,
                    latency_ms=round((time.monotonic() - started) * 1_000),
                    retry_count=attempt,
                    provider_model=str(response.get("model") or self.model),
                )
            except HTTPError as exc:
                error_body = exc.read(4_096).decode("utf-8", errors="replace").lower()
                balance_unavailable = "balance" in error_body and (
                    "insufficient" in error_body or "unavailable" in error_body
                )
                if exc.code == 402 or balance_unavailable:
                    raise DeepSeekBudgetUnavailable(
                        "DeepSeek account balance is unavailable"
                    ) from exc
                if (exc.code == 429 or exc.code >= 500) and attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise DeepSeekResponseError(
                    f"DeepSeek request failed with HTTP {exc.code}"
                ) from exc
            except (TimeoutError, socket.timeout, URLError) as exc:
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise DeepSeekError("DeepSeek request timed out or was unavailable") from exc
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise DeepSeekResponseError("DeepSeek returned a malformed response") from exc

        raise DeepSeekError("DeepSeek request was unavailable")
