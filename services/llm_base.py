from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMService(ABC):
    """Language model abstraction to hide provider specifics."""

    @abstractmethod
    def complete(self, messages: list[dict[str, Any]], model: str, **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def structured(self, messages: list[dict[str, Any]], model: str, schema: Any):
        """
        Optionally return structured data given a schema (pydantic/dataclass).
        Implementations may raise NotImplementedError if unsupported.
        """
        raise NotImplementedError
