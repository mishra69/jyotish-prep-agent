"""
Stateless chart API: birth data in, chart + dasha + yogas out.

Wraps the astro/ package and nothing else -- no LLM, no storage, no client
names. Deployed to Cloud Run; called by the Cloudflare Worker.

Run locally (health check is /health):
    API_KEY=dev venv/bin/uvicorn api.main:app --reload --port 8080
"""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from astro.serialization import chart_to_dict, dasha_to_dict, yogas_to_list
from astro.chart import generate_birth_chart
from astro.dasha import calculate_dasha
from astro.yogas import scan_yogas

API_VERSION = "1"

# Must match the kerykeion settings in astro/chart.py:_kerykeion_subject.
CHART_SETTINGS = {"ayanamsa": "lahiri", "house_system": "whole_sign", "zodiac": "sidereal"}

# Fields that identify the client. The math never needs them, so the API
# neither accepts nor returns them.
_PII_FIELDS = ("name", "birth_place")

app = FastAPI(title="Jyotish Chart API", version=API_VERSION)


class ChartRequest(BaseModel):
    birth_date: date
    birth_time: time = Field(
        description="Local time at the birth place, HH:MM. Seconds are accepted but ignored "
        "(kerykeion takes hour and minute only).",
    )
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = Field(
        default=None,
        description="IANA name, e.g. Asia/Kolkata. Resolved from coordinates if omitted.",
    )
    reference_date: date = Field(
        description="Date that determines the 'current' dasha. Explicit so results are reproducible.",
    )


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        # Fail closed: an unconfigured deploy must not become a public endpoint.
        raise HTTPException(503, "API_KEY not configured on server")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing X-API-Key")


@lru_cache(maxsize=1)
def _timezone_finder():
    from timezonefinder import TimezoneFinder
    return TimezoneFinder()


def resolve_timezone(req: ChartRequest) -> str:
    if req.timezone:
        try:
            ZoneInfo(req.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, f"Unknown timezone: {req.timezone!r}")
        return req.timezone
    tz = _timezone_finder().timezone_at(lat=req.latitude, lng=req.longitude)
    if not tz:
        # Never fall back to UTC: a wrong offset silently shifts the lagna,
        # every house, and the dasha.
        raise HTTPException(
            422, "Could not determine timezone for these coordinates; pass 'timezone' explicitly"
        )
    return tz


# Not /healthz: Cloud Run reserves paths ending in "z" on run.app URLs.
@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/chart", dependencies=[Depends(require_api_key)])
def chart(req: ChartRequest) -> dict:
    tz = resolve_timezone(req)
    try:
        birth_chart = generate_birth_chart(
            name="client",
            birth_date=req.birth_date,
            birth_time=req.birth_time,
            birth_place="",
            latitude=req.latitude,
            longitude=req.longitude,
            timezone=tz,
        )
    except ValueError as e:
        raise HTTPException(422, f"Chart computation failed: {e}")

    ref = datetime.combine(req.reference_date, time(12, 0))
    chart_dict = chart_to_dict(birth_chart)
    for field in _PII_FIELDS:
        chart_dict.pop(field, None)

    return {
        "meta": {"api_version": API_VERSION, "timezone": tz, **CHART_SETTINGS},
        "chart": chart_dict,
        "dasha": dasha_to_dict(calculate_dasha(birth_chart, reference_date=ref)),
        "yogas": yogas_to_list(scan_yogas(birth_chart)),
    }
