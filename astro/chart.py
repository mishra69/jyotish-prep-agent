"""
Birth chart (Kundli) generation using kerykeion + Swiss Ephemeris.
Sidereal zodiac, Lahiri ayanamsa, Whole Sign houses.
"""
from __future__ import annotations
from datetime import date, time, datetime

from kerykeion import AstrologicalSubject

from .models import (
    Planet, Sign, PlanetPosition, HouseData, BirthChart,
    SIGN_ORDER, SIGN_LORDS,
    get_nakshatra, sign_from_abs_degree, house_whole_sign,
)

# Maps kerykeion sign name strings → Sign enum
_SIGN_MAP: dict[str, Sign] = {s.value: s for s in Sign}

# kerykeion attribute names for each planet
_PLANET_ATTRS: dict[Planet, str] = {
    Planet.SUN:     "sun",
    Planet.MOON:    "moon",
    Planet.MARS:    "mars",
    Planet.MERCURY: "mercury",
    Planet.JUPITER: "jupiter",
    Planet.VENUS:   "venus",
    Planet.SATURN:  "saturn",
    Planet.RAHU:    "true_node",   # True North Node
}


def _kerykeion_subject(
    name: str,
    birth_date: date,
    birth_time: time,
    latitude: float,
    longitude: float,
    timezone: str,
) -> AstrologicalSubject:
    return AstrologicalSubject(
        name=name,
        year=birth_date.year,
        month=birth_date.month,
        day=birth_date.day,
        hour=birth_time.hour,
        minute=birth_time.minute,
        lat=latitude,
        lng=longitude,
        tz_str=timezone,
        zodiac_type="Sidereal",
        sidereal_mode="LAHIRI",
        houses_system_identifier="W",   # Whole Sign
        online=False,
    )


def _extract_planet(
    subj: AstrologicalSubject,
    planet: Planet,
    lagna_sign: Sign,
) -> PlanetPosition:
    attr = _PLANET_ATTRS[planet]
    p = getattr(subj, attr)
    abs_deg = p.abs_pos
    sign = _SIGN_MAP.get(p.sign, sign_from_abs_degree(abs_deg))
    nak, pada = get_nakshatra(abs_deg)
    house = house_whole_sign(sign, lagna_sign)
    return PlanetPosition(
        planet=planet,
        sign=sign,
        degree=p.position,
        abs_degree=abs_deg,
        house=house,
        nakshatra=nak,
        nakshatra_pada=pada,
        retrograde=bool(p.retrograde),
    )


def _extract_ketu(rahu: PlanetPosition, lagna_sign: Sign) -> PlanetPosition:
    ketu_abs = (rahu.abs_degree + 180.0) % 360.0
    ketu_sign = sign_from_abs_degree(ketu_abs)
    ketu_degree = ketu_abs % 30.0
    nak, pada = get_nakshatra(ketu_abs)
    house = house_whole_sign(ketu_sign, lagna_sign)
    return PlanetPosition(
        planet=Planet.KETU,
        sign=ketu_sign,
        degree=ketu_degree,
        abs_degree=ketu_abs,
        house=house,
        nakshatra=nak,
        nakshatra_pada=pada,
        retrograde=True,    # Ketu is always retrograde
    )


def generate_birth_chart(
    name: str,
    birth_date: date,
    birth_time: time,
    birth_place: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> BirthChart:
    """
    Compute a sidereal Jyotish birth chart.

    Args:
        name:        Client name (for labelling).
        birth_date:  Date of birth.
        birth_time:  Local time of birth.
        birth_place: City/place string (display only).
        latitude:    Geographic latitude (decimal degrees, S is negative).
        longitude:   Geographic longitude (decimal degrees, W is negative).
        timezone:    IANA timezone string, e.g. "Asia/Kolkata".

    Returns:
        BirthChart with all planetary positions, houses, and lagna.
    """
    subj = _kerykeion_subject(name, birth_date, birth_time, latitude, longitude, timezone)

    # Ascendant
    lagna_abs = subj.first_house.abs_pos
    lagna_sign = _SIGN_MAP.get(subj.first_house.sign, sign_from_abs_degree(lagna_abs))
    lagna_degree = lagna_abs % 30.0

    # Planets (Sun through Saturn + Rahu)
    positions: dict[str, PlanetPosition] = {}
    for planet in list(_PLANET_ATTRS.keys()):
        pos = _extract_planet(subj, planet, lagna_sign)
        positions[planet.value] = pos

    # Ketu (derived from Rahu)
    rahu_pos = positions[Planet.RAHU.value]
    ketu_pos = _extract_ketu(rahu_pos, lagna_sign)
    positions[Planet.KETU.value] = ketu_pos

    # Houses (Whole Sign: house N has the sign that is N-1 signs after lagna)
    lagna_idx = SIGN_ORDER.index(lagna_sign)
    houses: dict[int, HouseData] = {}
    for h in range(1, 13):
        sign = SIGN_ORDER[(lagna_idx + h - 1) % 12]
        houses[h] = HouseData(number=h, sign=sign, lord=SIGN_LORDS[sign])

    # Moon metadata
    moon_pos = positions[Planet.MOON.value]

    birth_dt = datetime.combine(birth_date, birth_time)

    return BirthChart(
        name=name,
        birth_datetime=birth_dt,
        birth_place=birth_place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        lagna=lagna_sign,
        lagna_degree=lagna_degree,
        moon_sign=moon_pos.sign,
        moon_nakshatra=moon_pos.nakshatra,
        moon_nakshatra_pada=moon_pos.nakshatra_pada,
        planets=positions,
        houses=houses,
    )
