from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


class OpenAIHTTPError(RuntimeError):
    pass


@dataclass
class OpenAIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: float = 60.0
    max_retries: int = 2
    retry_backoff_sec: float = 1.5


class OpenAIChatClient:
    """
    Minimal OpenAI Chat Completions HTTP client (no SDK dependency).

    Uses POST {base_url}/chat/completions and expects response.choices[0].message.content.
    """

    def __init__(self, config: OpenAIConfig):
        self.config = config

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        data: Dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        result = self._post_json("/chat/completions", data)
        try:
            return result["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise OpenAIHTTPError(f"Unexpected response shape: {result}") from exc

    def chat_json(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = 0.0,
        max_tokens: Optional[int] = None,
        expect_keys: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Ask the model to return strict JSON (best effort). Returns (obj, raw_text).
        """

        content = self.chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        obj = _extract_json_object(content)
        if expect_keys:
            for k in expect_keys:
                obj.setdefault(k, [] if k.endswith("s") else None)
        return obj, content

    def _post_json(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = self.config.base_url.rstrip("/") + path
        last_err: Optional[Exception] = None
        stripped_temperature = False
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers=self._headers(),
                    data=json.dumps(data),
                    timeout=self.config.timeout_sec,
                )
                if resp.status_code >= 400:
                    # Some models only support the default temperature. If we sent one, retry once
                    # without it for better compatibility.
                    if (
                        resp.status_code == 400
                        and not stripped_temperature
                        and "temperature" in data
                    ):
                        try:
                            j = resp.json()
                            err = j.get("error") if isinstance(j, dict) else None
                            if isinstance(err, dict) and err.get("param") == "temperature":
                                code = str(err.get("code") or "")
                                if code in ("unsupported_value", "invalid_request_error", "invalid_value") or "Unsupported value" in str(
                                    err.get("message") or ""
                                ):
                                    data.pop("temperature", None)
                                    stripped_temperature = True
                                    continue
                        except Exception:
                            pass
                    raise OpenAIHTTPError(f"{resp.status_code}: {resp.text}")
                return resp.json()
            except Exception as exc:  # pragma: no cover
                last_err = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(self.config.retry_backoff_sec * (attempt + 1))
        raise OpenAIHTTPError(f"OpenAI request failed: {last_err}") from last_err


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Best-effort JSON object extraction for model outputs.
    Accepts raw JSON or JSON fenced in markdown.
    """

    stripped = text.strip()
    # Remove markdown fences if present
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # drop first fence line and last fence line
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            stripped = "\n".join(lines[1:-1]).strip()
    # Some models prefix with "json"
    if stripped.lower().startswith("json"):
        stripped = stripped[4:].lstrip()
    # Parse
    return json.loads(stripped)
