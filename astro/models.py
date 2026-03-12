from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Planet(str, Enum):
    SUN = "Sun"
    MOON = "Moon"
    MARS = "Mars"
    MERCURY = "Mercury"
    JUPITER = "Jupiter"
    VENUS = "Venus"
    SATURN = "Saturn"
    RAHU = "Rahu"
    KETU = "Ketu"


class Sign(str, Enum):
    ARIES = "Aries"
    TAURUS = "Taurus"
    GEMINI = "Gemini"
    CANCER = "Cancer"
    LEO = "Leo"
    VIRGO = "Virgo"
    LIBRA = "Libra"
    SCORPIO = "Scorpio"
    SAGITTARIUS = "Sagittarius"
    CAPRICORN = "Capricorn"
    AQUARIUS = "Aquarius"
    PISCES = "Pisces"


class YogaConfidence(str, Enum):
    CONFIRMED = "confirmed"
    BORDERLINE = "borderline"
    NOT_FORMED = "not_formed"


SIGN_ORDER: list[Sign] = [
    Sign.ARIES, Sign.TAURUS, Sign.GEMINI, Sign.CANCER,
    Sign.LEO, Sign.VIRGO, Sign.LIBRA, Sign.SCORPIO,
    Sign.SAGITTARIUS, Sign.CAPRICORN, Sign.AQUARIUS, Sign.PISCES,
]

SIGN_LORDS: dict[Sign, Planet] = {
    Sign.ARIES: Planet.MARS,
    Sign.TAURUS: Planet.VENUS,
    Sign.GEMINI: Planet.MERCURY,
    Sign.CANCER: Planet.MOON,
    Sign.LEO: Planet.SUN,
    Sign.VIRGO: Planet.MERCURY,
    Sign.LIBRA: Planet.VENUS,
    Sign.SCORPIO: Planet.MARS,
    Sign.SAGITTARIUS: Planet.JUPITER,
    Sign.CAPRICORN: Planet.SATURN,
    Sign.AQUARIUS: Planet.SATURN,
    Sign.PISCES: Planet.JUPITER,
}

NAKSHATRAS: list[str] = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

NAK_SPAN = 360.0 / 27  # 13.333...°


def get_nakshatra(abs_degree: float) -> tuple[str, int]:
    """Return (nakshatra_name, pada 1-4) for a sidereal absolute degree."""
    idx = int(abs_degree / NAK_SPAN) % 27
    degree_in_nak = abs_degree % NAK_SPAN
    pada = int(degree_in_nak / (NAK_SPAN / 4)) + 1
    return NAKSHATRAS[idx], min(pada, 4)


def sign_from_abs_degree(abs_degree: float) -> Sign:
    idx = int(abs_degree / 30) % 12
    return SIGN_ORDER[idx]


def house_whole_sign(planet_sign: Sign, lagna_sign: Sign) -> int:
    """House number (1-12) using Whole Sign system."""
    lagna_idx = SIGN_ORDER.index(lagna_sign)
    planet_idx = SIGN_ORDER.index(planet_sign)
    return ((planet_idx - lagna_idx) % 12) + 1


@dataclass
class PlanetPosition:
    planet: Planet
    sign: Sign
    degree: float           # degrees within sign (0–30)
    abs_degree: float       # sidereal absolute degree (0–360)
    house: int              # 1–12 (Whole Sign)
    nakshatra: str
    nakshatra_pada: int     # 1–4
    retrograde: bool = False


@dataclass
class HouseData:
    number: int   # 1–12
    sign: Sign
    lord: Planet


@dataclass
class BirthChart:
    # Input
    name: str
    birth_datetime: datetime
    birth_place: str
    latitude: float
    longitude: float
    timezone: str

    # Computed
    lagna: Sign             # Ascendant sign
    lagna_degree: float     # Degree of ASC within sign
    moon_sign: Sign
    moon_nakshatra: str
    moon_nakshatra_pada: int

    planets: dict[str, PlanetPosition]   # Planet.value -> PlanetPosition
    houses: dict[int, HouseData]         # 1-12 -> HouseData


@dataclass
class DashaNode:
    planet: Planet
    start_date: datetime
    end_date: datetime
    level: int              # 0=Mahadasha, 1=Antardasha, 2=Pratyantardasha
    sub_dashas: list[DashaNode] = field(default_factory=list)

    @property
    def duration_years(self) -> float:
        delta = self.end_date - self.start_date
        return delta.days / 365.25


@dataclass
class DashaData:
    current_mahadasha: DashaNode
    current_antardasha: DashaNode
    next_transitions: list[DashaNode]   # next 3 Antardasha transitions
    mahadashas: list[DashaNode]         # full Mahadasha sequence from birth


@dataclass
class YogaResult:
    name: str
    sanskrit_name: str
    confidence: YogaConfidence
    planets_involved: list[str]         # Planet.value strings
    description: str
    formation_details: str              # why formed, borderline, or not
