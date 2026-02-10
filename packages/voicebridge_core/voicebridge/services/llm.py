from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMService(ABC):
    """Language model abstraction to hide provider specifics."""

    @abstractmethod
    def complete(self, messages: List[Dict[str, Any]], model: str, **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def structured(self, messages: List[Dict[str, Any]], model: str, schema: Any, **kwargs: Any):
        """
        Optionally return structured data given a schema (dataclass / pydantic / json schema).
        Implementations may raise NotImplementedError if unsupported.
        """

        raise NotImplementedError

