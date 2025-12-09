from __future__ import annotations

import json
import logging
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

    def complete(self, messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> str:
        params = {**self.default_params, **kwargs}
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                **params,
            )
            return response.choices[0].message.content or ""
        except APITimeoutError:
            self._log().warning("OpenAI LLM timeout; returning empty string.")
            return ""
        except APIError as exc:
            self._log().error("OpenAI LLM error: %s", exc)
            return ""

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
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                response_format={"type": "json_object"},
                **params,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except APITimeoutError:
            self._log().warning("OpenAI LLM timeout (structured); returning empty object.")
            return {}
        except APIError as exc:
            self._log().error("OpenAI LLM error (structured): %s", exc)
            return {}

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.llm_openai")
