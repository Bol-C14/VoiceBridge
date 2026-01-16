from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import APIError, APITimeoutError, OpenAI

from services.llm_base import LLMService


class OpenAILLMService(LLMService):
    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o-mini",
        default_params: dict[str, Any] | None = None,
    ):
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model
        self.default_params = default_params or {}
        self.metrics_hook = None

    def _emit_metrics(self, payload: dict[str, Any]) -> None:
        hook = getattr(self, "metrics_hook", None)
        if not callable(hook):
            return
        try:
            hook(payload)
        except Exception:
            self._log().warning("Failed to emit LLM metrics.")

    def _input_chars(self, messages: list[dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += len(content) if isinstance(content, str) else len(str(content))
        return total

    def complete(self, messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> str:
        params = {**self.default_params, **kwargs}
        input_chars = self._input_chars(messages)
        started = time.monotonic()
        output = ""
        error = None
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                **params,
            )
            output = response.choices[0].message.content or ""
            return output
        except APITimeoutError:
            error = "timeout"
            self._log().warning("OpenAI LLM timeout; returning empty string.")
            return ""
        except APIError as exc:
            error = str(exc)
            self._log().error("OpenAI LLM error: %s", exc)
            return ""
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            self._emit_metrics(
                {
                    "service": "llm",
                    "method": "complete",
                    "model": model or self.default_model,
                    "latency_ms": latency_ms,
                    "input_chars": input_chars,
                    "output_chars": len(output),
                    "success": error is None,
                    "error": error,
                }
            )

    def structured(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        schema: Any = None,
    ):
        """
        Returns a JSON object parsed from the model response.
        Schema (if provided) is advisory; no validation is applied here.
        """
        params = {**self.default_params}
        response_format: dict[str, Any] = {"type": "json_object"}
        if schema:
            try:
                response_format = {"type": "json_schema", "json_schema": schema}
            except Exception:
                response_format = {"type": "json_object"}
        input_chars = self._input_chars(messages)
        started = time.monotonic()
        payload: Any = {}
        error = None
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                response_format=response_format,
                **params,
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            return payload
        except json.JSONDecodeError as exc:
            error = "json_decode"
            self._log().error("Failed to decode structured response JSON: %s", exc)
            return {}
        except APITimeoutError:
            error = "timeout"
            self._log().warning("OpenAI LLM timeout (structured); returning empty object.")
            return {}
        except APIError as exc:
            error = str(exc)
            self._log().error("OpenAI LLM error (structured): %s", exc)
            return {}
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                output_chars = len(json.dumps(payload, ensure_ascii=True))
            except Exception:
                output_chars = 0
            self._emit_metrics(
                {
                    "service": "llm",
                    "method": "structured",
                    "model": model or self.default_model,
                    "latency_ms": latency_ms,
                    "input_chars": input_chars,
                    "output_chars": output_chars,
                    "success": error is None,
                    "error": error,
                }
            )

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.llm_openai")
