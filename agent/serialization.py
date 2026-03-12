"""
Helpers to convert astro dataclasses → plain dicts for LangGraph state storage.
"""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, date, time
from enum import Enum
from typing import Any

from astro.models import BirthChart, DashaData, YogaResult


def _default(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    raise TypeError(f"Unserializable: {type(obj)}")


def _to_dict(obj: Any) -> Any:
    return json.loads(json.dumps(asdict(obj), default=_default))


def chart_to_dict(chart: BirthChart) -> dict:
    return _to_dict(chart)


def dasha_to_dict(dasha: DashaData) -> dict:
    return _to_dict(dasha)


def yogas_to_list(yogas: list[YogaResult]) -> list[dict]:
    return [_to_dict(y) for y in yogas]
