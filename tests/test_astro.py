"""
Unit tests for the astro computation engine.
Test chart: Priya S., 15-Mar-1990, 14:32 IST, Bangalore
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, time, datetime
from astro.chart import generate_birth_chart
from astro.dasha import calculate_dasha
from astro.yogas import scan_yogas, filter_yogas
from astro.models import Planet, Sign, YogaConfidence

# ── Fixture ───────────────────────────────────────────────────────────────────

def priya_chart():
    return generate_birth_chart(
        name="Priya S.",
        birth_date=date(1990, 3, 15),
        birth_time=time(14, 32),
        birth_place="Bangalore",
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
    )

# ── Chart tests ───────────────────────────────────────────────────────────────

def test_lagna():
    chart = priya_chart()
    assert chart.lagna == Sign.CANCER, f"Expected Cancer lagna, got {chart.lagna}"

def test_moon_sign():
    chart = priya_chart()
    assert chart.moon_sign == Sign.LIBRA, f"Expected Libra moon, got {chart.moon_sign}"

def test_moon_nakshatra():
    chart = priya_chart()
    assert chart.moon_nakshatra == "Swati", f"Expected Swati, got {chart.moon_nakshatra}"

def test_all_planets_present():
    chart = priya_chart()
    for planet in Planet:
        assert planet.value in chart.planets, f"Missing planet: {planet.value}"

def test_houses_complete():
    chart = priya_chart()
    assert len(chart.houses) == 12, f"Expected 12 houses, got {len(chart.houses)}"
    for i in range(1, 13):
        assert i in chart.houses, f"Missing house {i}"

def test_whole_sign_houses():
    """In Whole Sign, house 1 sign == lagna sign."""
    chart = priya_chart()
    assert chart.houses[1].sign == chart.lagna

def test_ketu_opposite_rahu():
    """Ketu should be exactly 180° from Rahu."""
    chart = priya_chart()
    rahu = chart.planets[Planet.RAHU.value].abs_degree
    ketu = chart.planets[Planet.KETU.value].abs_degree
    diff = abs(rahu - ketu)
    if diff > 180:
        diff = 360 - diff
    assert abs(diff - 180) < 0.01, f"Rahu-Ketu diff should be 180°, got {diff}"

def test_planet_degrees_in_range():
    chart = priya_chart()
    for name, pos in chart.planets.items():
        assert 0 <= pos.abs_degree < 360, f"{name} abs_degree out of range: {pos.abs_degree}"
        assert 0 <= pos.degree < 30, f"{name} degree out of range: {pos.degree}"
        assert 1 <= pos.house <= 12, f"{name} house out of range: {pos.house}"

def test_nakshatra_pada_in_range():
    chart = priya_chart()
    for name, pos in chart.planets.items():
        assert 1 <= pos.nakshatra_pada <= 4, f"{name} pada out of range: {pos.nakshatra_pada}"

# ── Dasha tests ───────────────────────────────────────────────────────────────

def test_dasha_returns_current():
    chart = priya_chart()
    dasha = calculate_dasha(chart, reference_date=datetime(2024, 6, 1))
    assert dasha.current_mahadasha is not None
    assert dasha.current_antardasha is not None

def test_dasha_current_contains_reference_date():
    chart = priya_chart()
    ref = datetime(2024, 6, 1)
    dasha = calculate_dasha(chart, reference_date=ref)
    maha = dasha.current_mahadasha
    antar = dasha.current_antardasha
    assert maha.start_date <= ref < maha.end_date, "Reference date not inside mahadasha"
    assert antar.start_date <= ref < antar.end_date, "Reference date not inside antardasha"

def test_dasha_antardasha_sum():
    """Antardasha periods should sum close to mahadasha duration (within 7 days for float rounding)."""
    chart = priya_chart()
    dasha = calculate_dasha(chart)
    maha = dasha.current_mahadasha
    total_days = sum((a.end_date - a.start_date).days for a in maha.sub_dashas)
    maha_days = (maha.end_date - maha.start_date).days
    assert abs(total_days - maha_days) <= 7, f"Antardasha sum mismatch: {total_days} vs {maha_days}"

def test_dasha_next_transitions():
    chart = priya_chart()
    dasha = calculate_dasha(chart)
    assert len(dasha.next_transitions) > 0

def test_dasha_mahadashas_count():
    """We build exactly 9 mahadashas (one full cycle from Moon nakshatra lord)."""
    chart = priya_chart()
    dasha = calculate_dasha(chart)
    assert len(dasha.mahadashas) == 9, f"Expected 9 mahadashas, got {len(dasha.mahadashas)}"

# ── Yoga tests ────────────────────────────────────────────────────────────────

def test_yogas_returns_list():
    chart = priya_chart()
    yogas = scan_yogas(chart)
    assert isinstance(yogas, list)
    assert len(yogas) > 0

def test_yoga_confidence_values():
    chart = priya_chart()
    yogas = scan_yogas(chart)
    valid = {YogaConfidence.CONFIRMED, YogaConfidence.BORDERLINE, YogaConfidence.NOT_FORMED}
    for y in yogas:
        assert y.confidence in valid, f"Invalid confidence: {y.confidence}"

def test_ruchaka_yoga_present():
    """Mars exalted in Capricorn (house 7, a kendra) — Ruchaka should be confirmed."""
    chart = priya_chart()
    yogas = scan_yogas(chart)
    ruchaka = next((y for y in yogas if "Ruchaka" in y.name), None)
    assert ruchaka is not None, "Ruchaka yoga not found"
    assert ruchaka.confidence == YogaConfidence.CONFIRMED, f"Ruchaka should be confirmed, got {ruchaka.confidence}"

def test_filter_yogas_removes_not_formed():
    chart = priya_chart()
    yogas = filter_yogas(scan_yogas(chart))
    assert all(y.confidence != YogaConfidence.NOT_FORMED for y in yogas)

def test_yoga_has_required_fields():
    chart = priya_chart()
    yogas = scan_yogas(chart)
    for y in yogas:
        assert y.name, "Yoga missing name"
        assert y.formation_details, "Yoga missing formation_details"
        assert isinstance(y.planets_involved, list)


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
