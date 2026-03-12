"""
Vimshottari Dasha calculator.
Computes the full Mahadasha tree with Antardasha sub-periods.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from .models import Planet, BirthChart, DashaNode, DashaData, NAKSHATRAS, NAK_SPAN

# Vimshottari sequence and year-lengths (total = 120 years)
DASHA_SEQUENCE: list[Planet] = [
    Planet.KETU, Planet.VENUS, Planet.SUN, Planet.MOON,
    Planet.MARS, Planet.RAHU, Planet.JUPITER, Planet.SATURN, Planet.MERCURY,
]

DASHA_YEARS: dict[Planet, float] = {
    Planet.KETU:    7.0,
    Planet.VENUS:   20.0,
    Planet.SUN:     6.0,
    Planet.MOON:    10.0,
    Planet.MARS:    7.0,
    Planet.RAHU:    18.0,
    Planet.JUPITER: 16.0,
    Planet.SATURN:  19.0,
    Planet.MERCURY: 17.0,
}

# Nakshatra lord for each nakshatra (index matches NAKSHATRAS list)
NAKSHATRA_LORDS: list[Planet] = [
    Planet.KETU,     # 0  Ashwini
    Planet.VENUS,    # 1  Bharani
    Planet.SUN,      # 2  Krittika
    Planet.MOON,     # 3  Rohini
    Planet.MARS,     # 4  Mrigashira
    Planet.RAHU,     # 5  Ardra
    Planet.JUPITER,  # 6  Punarvasu
    Planet.SATURN,   # 7  Pushya
    Planet.MERCURY,  # 8  Ashlesha
    Planet.KETU,     # 9  Magha
    Planet.VENUS,    # 10 Purva Phalguni
    Planet.SUN,      # 11 Uttara Phalguni
    Planet.MOON,     # 12 Hasta
    Planet.MARS,     # 13 Chitra
    Planet.RAHU,     # 14 Swati
    Planet.JUPITER,  # 15 Vishakha
    Planet.SATURN,   # 16 Anuradha
    Planet.MERCURY,  # 17 Jyeshtha
    Planet.KETU,     # 18 Mula
    Planet.VENUS,    # 19 Purva Ashadha
    Planet.SUN,      # 20 Uttara Ashadha
    Planet.MOON,     # 21 Shravana
    Planet.MARS,     # 22 Dhanishtha
    Planet.RAHU,     # 23 Shatabhisha
    Planet.JUPITER,  # 24 Purva Bhadrapada
    Planet.SATURN,   # 25 Uttara Bhadrapada
    Planet.MERCURY,  # 26 Revati
]

TOTAL_YEARS = 120.0


def _years_to_days(years: float) -> float:
    return years * 365.25


def _td(years: float) -> timedelta:
    return timedelta(days=_years_to_days(years))


def _starting_dasha(moon_abs_degree: float) -> tuple[Planet, float]:
    """
    Return (starting_planet, remaining_years_in_first_dasha).
    Based on Moon's position within its nakshatra at birth.
    """
    nak_idx = int(moon_abs_degree / NAK_SPAN) % 27
    starting_planet = NAKSHATRA_LORDS[nak_idx]

    fraction_traversed = (moon_abs_degree % NAK_SPAN) / NAK_SPAN
    remaining_years = (1.0 - fraction_traversed) * DASHA_YEARS[starting_planet]
    return starting_planet, remaining_years


def _build_antardashas(
    mahadasha_planet: Planet,
    maha_start: datetime,
    maha_end: datetime,
) -> list[DashaNode]:
    """
    Build Antardasha sub-periods within a Mahadasha.
    Antardasha duration = (antar_years × maha_years) / TOTAL_YEARS
    """
    maha_years = DASHA_YEARS[mahadasha_planet]
    maha_idx = DASHA_SEQUENCE.index(mahadasha_planet)

    antardashas: list[DashaNode] = []
    current = maha_start

    for i in range(9):
        antar_planet = DASHA_SEQUENCE[(maha_idx + i) % 9]
        antar_years = (DASHA_YEARS[antar_planet] * maha_years) / TOTAL_YEARS
        antar_end = current + _td(antar_years)
        antardashas.append(DashaNode(
            planet=antar_planet,
            start_date=current,
            end_date=antar_end,
            level=1,
        ))
        current = antar_end

    # Clamp last antardasha end to mahadasha end (floating point drift)
    if antardashas:
        antardashas[-1].end_date = maha_end

    return antardashas


def _build_mahadashas(
    birth_dt: datetime,
    starting_planet: Planet,
    remaining_first_years: float,
) -> list[DashaNode]:
    """Build full Mahadasha sequence from birth."""
    start_idx = DASHA_SEQUENCE.index(starting_planet)
    mahadashas: list[DashaNode] = []
    current = birth_dt

    for i in range(9):
        planet = DASHA_SEQUENCE[(start_idx + i) % 9]
        years = remaining_first_years if i == 0 else DASHA_YEARS[planet]
        end = current + _td(years)

        node = DashaNode(
            planet=planet,
            start_date=current,
            end_date=end,
            level=0,
        )
        node.sub_dashas = _build_antardashas(planet, current, end)
        mahadashas.append(node)
        current = end

    return mahadashas


def _find_current(nodes: list[DashaNode], now: datetime) -> DashaNode | None:
    for node in nodes:
        if node.start_date <= now < node.end_date:
            return node
    return nodes[-1] if nodes else None


def calculate_dasha(chart: BirthChart, reference_date: datetime | None = None) -> DashaData:
    """
    Compute Vimshottari dasha periods for a birth chart.

    Args:
        chart:          BirthChart (must include Moon's abs_degree).
        reference_date: Date to determine "current" period (defaults to now).

    Returns:
        DashaData with current Mahadasha, Antardasha, next transitions.
    """
    if reference_date is None:
        reference_date = datetime.now()

    moon_abs = chart.planets[Planet.MOON.value].abs_degree
    starting_planet, remaining_years = _starting_dasha(moon_abs)

    mahadashas = _build_mahadashas(chart.birth_datetime, starting_planet, remaining_years)

    current_maha = _find_current(mahadashas, reference_date)
    current_antar = _find_current(current_maha.sub_dashas, reference_date) if current_maha else None

    # Next 3 antardasha transitions
    next_transitions: list[DashaNode] = []
    if current_maha:
        all_antars = current_maha.sub_dashas[:]
        # Also pull first antardasha from next mahadasha
        maha_idx = mahadashas.index(current_maha)
        if maha_idx + 1 < len(mahadashas):
            all_antars += mahadashas[maha_idx + 1].sub_dashas[:2]

        future = [a for a in all_antars if a.start_date > reference_date]
        next_transitions = future[:3]

    return DashaData(
        current_mahadasha=current_maha,
        current_antardasha=current_antar,
        next_transitions=next_transitions,
        mahadashas=mahadashas,
    )
