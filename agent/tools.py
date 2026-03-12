"""
LangGraph tools:
  - compute_chart / compute_dasha / compute_yogas  (wrap Phase 1 astro engine)
  - ask_human  (HITL: agent calls this when uncertain; uses interrupt() to pause)
"""
from __future__ import annotations
from datetime import date, time, datetime

from langchain_core.tools import tool
from langgraph.types import interrupt

from astro.chart import generate_birth_chart
from astro.dasha import calculate_dasha
from astro.yogas import scan_yogas
from agent.serialization import chart_to_dict, dasha_to_dict, yogas_to_list


# ── Astro computation tools ───────────────────────────────────────────────────

@tool
def tool_compute_chart(
    client_name: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> dict:
    """
    Generate a sidereal Jyotish birth chart (Kundli) using Swiss Ephemeris.

    Args:
        client_name: Client's name.
        birth_date:  Date of birth in YYYY-MM-DD format.
        birth_time:  Local time of birth in HH:MM format.
        birth_place: City/place name (for display).
        latitude:    Geographic latitude (decimal, S negative).
        longitude:   Geographic longitude (decimal, W negative).
        timezone:    IANA timezone string (e.g. 'Asia/Kolkata').

    Returns:
        Serialized BirthChart dict.
    """
    bd = date.fromisoformat(birth_date)
    bt_parts = birth_time.split(":")
    bt = time(int(bt_parts[0]), int(bt_parts[1]))
    chart = generate_birth_chart(client_name, bd, bt, birth_place, latitude, longitude, timezone)
    return chart_to_dict(chart)


@tool
def tool_compute_dasha(birth_chart: dict) -> dict:
    """
    Calculate Vimshottari dasha periods from a birth chart.

    Args:
        birth_chart: Serialized BirthChart dict (output of tool_compute_chart).

    Returns:
        Serialized DashaData dict with current Mahadasha, Antardasha, and next transitions.
    """
    from astro.models import BirthChart, PlanetPosition, HouseData, Planet, Sign, SIGN_LORDS
    # Reconstruct minimal BirthChart from dict for dasha calculation
    # We only need birth_datetime and moon abs_degree
    planets = {}
    for pname, pdata in birth_chart.get("planets", {}).items():
        planets[pname] = PlanetPosition(
            planet=Planet(pname),
            sign=Sign(pdata["sign"]),
            degree=pdata["degree"],
            abs_degree=pdata["abs_degree"],
            house=pdata["house"],
            nakshatra=pdata["nakshatra"],
            nakshatra_pada=pdata["nakshatra_pada"],
            retrograde=pdata.get("retrograde", False),
        )

    chart = BirthChart(
        name=birth_chart["name"],
        birth_datetime=datetime.fromisoformat(birth_chart["birth_datetime"]),
        birth_place=birth_chart["birth_place"],
        latitude=birth_chart["latitude"],
        longitude=birth_chart["longitude"],
        timezone=birth_chart["timezone"],
        lagna=Sign(birth_chart["lagna"]),
        lagna_degree=birth_chart["lagna_degree"],
        moon_sign=Sign(birth_chart["moon_sign"]),
        moon_nakshatra=birth_chart["moon_nakshatra"],
        moon_nakshatra_pada=birth_chart["moon_nakshatra_pada"],
        planets=planets,
        houses={},   # not needed for dasha
    )
    dasha = calculate_dasha(chart)
    return dasha_to_dict(dasha)


@tool
def tool_compute_yogas(birth_chart: dict) -> list:
    """
    Scan a birth chart for major Jyotish yogas (planetary combinations).

    Args:
        birth_chart: Serialized BirthChart dict (output of tool_compute_chart).

    Returns:
        List of YogaResult dicts. Each has: name, confidence (confirmed/borderline/not_formed),
        planets_involved, description, formation_details.
    """
    from astro.models import BirthChart, PlanetPosition, HouseData, Planet, Sign, SIGN_LORDS
    from astro.yogas import scan_yogas

    planets = {}
    for pname, pdata in birth_chart.get("planets", {}).items():
        planets[pname] = PlanetPosition(
            planet=Planet(pname),
            sign=Sign(pdata["sign"]),
            degree=pdata["degree"],
            abs_degree=pdata["abs_degree"],
            house=pdata["house"],
            nakshatra=pdata["nakshatra"],
            nakshatra_pada=pdata["nakshatra_pada"],
            retrograde=pdata.get("retrograde", False),
        )

    houses = {}
    for h_num_str, h_data in birth_chart.get("houses", {}).items():
        h_num = int(h_num_str)
        houses[h_num] = HouseData(
            number=h_num,
            sign=Sign(h_data["sign"]),
            lord=Planet(h_data["lord"]),
        )

    chart = BirthChart(
        name=birth_chart["name"],
        birth_datetime=datetime.fromisoformat(birth_chart["birth_datetime"]),
        birth_place=birth_chart["birth_place"],
        latitude=birth_chart["latitude"],
        longitude=birth_chart["longitude"],
        timezone=birth_chart["timezone"],
        lagna=Sign(birth_chart["lagna"]),
        lagna_degree=birth_chart["lagna_degree"],
        moon_sign=Sign(birth_chart["moon_sign"]),
        moon_nakshatra=birth_chart["moon_nakshatra"],
        moon_nakshatra_pada=birth_chart["moon_nakshatra_pada"],
        planets=planets,
        houses=houses,
    )

    yogas = scan_yogas(chart)
    return yogas_to_list(yogas)


# ── Human-as-a-Tool ───────────────────────────────────────────────────────────

@tool
def ask_human(question: str) -> str:
    """
    Ask the astrologer a clarifying question when uncertain about a chart pattern.

    Use this when:
    - A yoga's formation is borderline or ambiguous
    - Two classical rules give contradictory readings
    - A planet is near a house cusp (within ~1°)
    - The topic involves sensitive areas (health, timing) where astrologer emphasis matters
    - Any configuration you find unusual

    Always provide context: what you observe, what the ambiguity is.

    Args:
        question: The specific question for the astrologer, with chart context.

    Returns:
        The astrologer's answer as a string.
    """
    # interrupt() pauses graph execution. The UI collects the answer and resumes.
    answer = interrupt({"type": "ask_human", "question": question})
    return str(answer)


# All tools available to the synthesis LLM
SYNTHESIS_TOOLS = [ask_human]
COMPUTATION_TOOLS = [tool_compute_chart, tool_compute_dasha, tool_compute_yogas]
