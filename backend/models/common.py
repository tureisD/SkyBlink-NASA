"""Shared enums, base models, and contract constants."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Base for contract models. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FlagStatus(str, Enum):
    NOMINAL = "NOMINAL"
    CAUTION = "CAUTION"
    ALERT = "ALERT"


class Confidence(str, Enum):
    HIGH = "high"
    LOW = "low"


TargetId = Literal[
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
]

EPOCH_ID_PATTERN = r"^\d{4}_E\d+$"
