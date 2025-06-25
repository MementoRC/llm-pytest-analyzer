"""Generic task input/result models for LLM Task Framework."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar("T", bound="SerializableModel")


class SerializableModel:
    """
    Base class for serializable models.
    """

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(**data)


@dataclass
class GenericTaskInput(SerializableModel):
    """
    Generic input model for tasks.
    """

    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenericTaskResult(SerializableModel):
    """
    Generic result model for tasks.
    """

    result: Any
    success: bool = True
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
