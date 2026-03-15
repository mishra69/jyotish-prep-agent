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
from astro.models import Planet, Sign, YogaConfidence, SIGN_ORDER

# ── Fixtures (computed once at import time) ───────────────────────────────────

def _make_chart():
    return generate_birth_chart(
        name="Priya S.",
        birth_date=date(1990, 3, 15),
        birth_time=time(14, 32),
        birth_place="Bangalore",
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
    )

CHART = _make_chart()
DASHA = calculate_dasha(CHART)

# ── Chart tests ───────────────────────────────────────────────────────────────

def test_lagna():
    assert CHART.lagna == Sign.CANCER, f"Expected Cancer lagna, got {CHART.lagna}"

def test_moon_sign():
    assert CHART.moon_sign == Sign.LIBRA, f"Expected Libra moon, got {CHART.moon_sign}"

def test_moon_nakshatra():
    assert CHART.moon_nakshatra == "Swati", f"Expected Swati, got {CHART.moon_nakshatra}"

def test_all_planets_present():
    for planet in Planet:
        assert planet.value in CHART.planets, f"Missing planet: {planet.value}"

def test_houses_complete():
    assert len(CHART.houses) == 12, f"Expected 12 houses, got {len(CHART.houses)}"
    for i in range(1, 13):
        assert i in CHART.houses, f"Missing house {i}"

def test_whole_sign_all_signs_unique():
    """Whole Sign: each of the 12 signs appears exactly once across the 12 houses."""
    signs = [h.sign for h in CHART.houses.values()]
    assert len(set(signs)) == 12, f"Expected 12 unique signs, got {len(set(signs))}: {signs}"

def test_whole_sign_house1_is_lagna():
    assert CHART.houses[1].sign == CHART.lagna

def test_whole_sign_houses_sequential():
    """Each house sign should be the next sign after the previous one."""
    signs_in_order = [CHART.houses[h].sign for h in range(1, 13)]
    for i in range(12):
        expected_next = SIGN_ORDER[(SIGN_ORDER.index(signs_in_order[i]) + 1) % 12]
        actual_next = signs_in_order[(i + 1) % 12]
        assert expected_next == actual_next, f"House {i+1}→{i+2} sign sequence broken"

def test_ketu_opposite_rahu():
    """Ketu must be exactly 180° from Rahu (we compute this ourselves)."""
    rahu = CHART.planets[Planet.RAHU.value].abs_degree
    ketu = CHART.planets[Planet.KETU.value].abs_degree
    diff = abs(rahu - ketu)
    if diff > 180:
        diff = 360 - diff
    assert abs(diff - 180) < 0.01, f"Rahu-Ketu diff should be 180°, got {diff}"

def test_planet_degrees_in_range():
    for name, pos in CHART.planets.items():
        assert 0 <= pos.abs_degree < 360, f"{name} abs_degree out of range: {pos.abs_degree}"
        assert 0 <= pos.degree < 30, f"{name} sign-degree out of range: {pos.degree}"
        assert 1 <= pos.house <= 12, f"{name} house out of range: {pos.house}"

def test_nakshatra_pada_in_range():
    for name, pos in CHART.planets.items():
        assert 1 <= pos.nakshatra_pada <= 4, f"{name} pada out of range: {pos.nakshatra_pada}"

def test_planet_house_matches_sign():
    """Planet's house number must match where its sign falls relative to lagna (Whole Sign)."""
    lagna_idx = SIGN_ORDER.index(CHART.lagna)
    for name, pos in CHART.planets.items():
        expected_house = (SIGN_ORDER.index(pos.sign) - lagna_idx) % 12 + 1
        assert pos.house == expected_house, (
            f"{name}: sign {pos.sign} should be house {expected_house}, got {pos.house}"
        )

# ── Dasha invariant tests ─────────────────────────────────────────────────────

def test_dasha_returns_current():
    dasha = calculate_dasha(CHART, reference_date=datetime(2024, 6, 1))
    assert dasha.current_mahadasha is not None
    assert dasha.current_antardasha is not None

def test_dasha_current_contains_reference_date():
    ref = datetime(2024, 6, 1)
    dasha = calculate_dasha(CHART, reference_date=ref)
    maha = dasha.current_mahadasha
    antar = dasha.current_antardasha
    assert maha.start_date <= ref < maha.end_date, "Reference date not inside mahadasha"
    assert antar.start_date <= ref < antar.end_date, "Reference date not inside antardasha"

def test_dasha_mahadashas_count():
    """Vimshottari cycle is always exactly 9 mahadashas."""
    assert len(DASHA.mahadashas) == 9, f"Expected 9 mahadashas, got {len(DASHA.mahadashas)}"

def test_dasha_total_duration_at_most_120_years():
    """9 mahadashas span at most 120 years (first is partial — the birth balance)."""
    total_days = sum((m.end_date - m.start_date).days for m in DASHA.mahadashas)
    assert total_days <= 120 * 365.25 + 2, f"Total dasha exceeds 120 years: {total_days} days"
    assert total_days > 0, "Total dasha duration is zero"

def test_dasha_periods_contiguous():
    """Mahadasha periods must be contiguous — end of one == start of next."""
    mahadashas = sorted(DASHA.mahadashas, key=lambda m: m.start_date)
    for i in range(len(mahadashas) - 1):
        assert mahadashas[i].end_date == mahadashas[i + 1].start_date, (
            f"Gap/overlap between mahadasha {i} and {i+1}"
        )

def test_antardasha_sum_equals_mahadasha():
    """Antardasha periods must sum to their mahadasha duration (within 2 days for float rounding)."""
    for maha in DASHA.mahadashas:
        total = sum((a.end_date - a.start_date).days for a in maha.sub_dashas)
        expected = (maha.end_date - maha.start_date).days
        assert abs(total - expected) <= 5, (
            f"{maha.planet} mahadasha: antardasha sum {total} ≠ {expected} days"
        )

def test_antardasha_periods_contiguous():
    """Antardasha periods within each mahadasha must be contiguous."""
    for maha in DASHA.mahadashas:
        sub = sorted(maha.sub_dashas, key=lambda a: a.start_date)
        for i in range(len(sub) - 1):
            assert sub[i].end_date == sub[i + 1].start_date, (
                f"Gap in {maha.planet} antardashas between period {i} and {i+1}"
            )

def test_dasha_next_transitions():
    assert len(DASHA.next_transitions) > 0

# ── Yoga tests ────────────────────────────────────────────────────────────────

YOGAS = scan_yogas(CHART)

def test_yogas_returns_list():
    assert isinstance(YOGAS, list)
    assert len(YOGAS) > 0

def test_yoga_confidence_values():
    valid = {YogaConfidence.CONFIRMED, YogaConfidence.BORDERLINE, YogaConfidence.NOT_FORMED}
    for y in YOGAS:
        assert y.confidence in valid, f"Invalid confidence: {y.confidence}"

def test_ruchaka_yoga_present():
    """Mars exalted in Capricorn (house 7, a kendra) — Ruchaka should be confirmed."""
    ruchaka = next((y for y in YOGAS if "Ruchaka" in y.name), None)
    assert ruchaka is not None, "Ruchaka yoga not found"
    assert ruchaka.confidence == YogaConfidence.CONFIRMED, f"Ruchaka should be confirmed, got {ruchaka.confidence}"

def test_filter_yogas_removes_not_formed():
    filtered = filter_yogas(YOGAS)
    assert all(y.confidence != YogaConfidence.NOT_FORMED for y in filtered)

def test_yoga_has_required_fields():
    for y in YOGAS:
        assert y.name, "Yoga missing name"
        assert y.formation_details, "Yoga missing formation_details"
        assert isinstance(y.planets_involved, list)


# ── Parametric fixture set ────────────────────────────────────────────────────
#
# Each entry exercises a different quirk. The invariant tests below run against
# ALL of these, so any input-specific bug will surface.

PARAM_FIXTURES = [
    # India — no DST, UTC+5:30 fixed
    dict(id="india_no_dst", name="Priya S.", birth_date=date(1990, 3, 15),
         birth_time=time(14, 32), birth_place="Bangalore", lat=12.9716, lon=77.5946,
         tz="Asia/Kolkata"),

    # US East, summer → EDT (UTC-4)
    dict(id="us_east_summer_dst", name="Alex R.", birth_date=date(1985, 7, 4),
         birth_time=time(9, 15), birth_place="New York", lat=40.7128, lon=-74.0060,
         tz="America/New_York"),

    # US East, winter → EST (UTC-5), near midnight
    dict(id="us_east_winter_standard", name="Sarah M.", birth_date=date(1975, 12, 21),
         birth_time=time(23, 45), birth_place="Boston", lat=42.3601, lon=-71.0589,
         tz="America/New_York"),

    # US Midwest, born just before spring-forward gap (2 AM → 3 AM, April 6 2003)
    dict(id="us_spring_forward_before_gap", name="Chris L.", birth_date=date(2003, 4, 6),
         birth_time=time(1, 30), birth_place="Chicago", lat=41.8781, lon=-87.6298,
         tz="America/Chicago"),

    # US Midwest, born just after spring-forward gap (time 2:xx didn't exist)
    dict(id="us_spring_forward_after_gap", name="Dana K.", birth_date=date(2003, 4, 6),
         birth_time=time(3, 30), birth_place="Chicago", lat=41.8781, lon=-87.6298,
         tz="America/Chicago"),

    # US East, born during fall-back ambiguous hour (1:30 AM occurs twice on Nov 2 2003)
    dict(id="us_fall_back_ambiguous", name="Morgan P.", birth_date=date(2003, 11, 2),
         birth_time=time(1, 30), birth_place="New York", lat=40.7128, lon=-74.0060,
         tz="America/New_York"),

    # Arizona — US state that never observes DST
    dict(id="us_arizona_no_dst", name="Maria G.", birth_date=date(1998, 6, 15),
         birth_time=time(12, 0), birth_place="Phoenix", lat=33.4484, lon=-112.0740,
         tz="America/Phoenix"),

    # US West Coast, summer → PDT (UTC-7)
    dict(id="us_west_summer_dst", name="Pacific Pat", birth_date=date(1978, 8, 20),
         birth_time=time(3, 0), birth_place="Los Angeles", lat=34.0522, lon=-118.2437,
         tz="America/Los_Angeles"),

    # Nepal — UTC+5:45, one of the few 45-minute offset timezones
    dict(id="nepal_utc545", name="Arjun T.", birth_date=date(1982, 9, 10),
         birth_time=time(6, 0), birth_place="Kathmandu", lat=27.7172, lon=85.3240,
         tz="Asia/Kathmandu"),

    # Iran — UTC+3:30 standard, +4:30 DST (fractional + DST combo)
    dict(id="iran_fractional_dst", name="Leila F.", birth_date=date(1991, 5, 20),
         birth_time=time(11, 0), birth_place="Tehran", lat=35.6892, lon=51.3890,
         tz="Asia/Tehran"),

    # Southern hemisphere, southern summer (Sydney observes DST in Jan → AEDT UTC+11)
    dict(id="australia_summer_dst", name="Emma W.", birth_date=date(1995, 1, 15),
         birth_time=time(8, 30), birth_place="Sydney", lat=-33.8688, lon=151.2093,
         tz="Australia/Sydney"),

    # Southern hemisphere, no DST (Johannesburg, SAST = UTC+2 year-round)
    dict(id="south_africa_no_dst", name="Thabo M.", birth_date=date(1988, 6, 21),
         birth_time=time(7, 0), birth_place="Johannesburg", lat=-26.2041, lon=28.0473,
         tz="Africa/Johannesburg"),

    # Very old date — pre-WWII (historical ephemeris accuracy check)
    dict(id="very_old_date", name="Elder", birth_date=date(1925, 3, 21),
         birth_time=time(12, 0), birth_place="London", lat=51.5074, lon=-0.1278,
         tz="Europe/London"),

    # Leap day birth
    dict(id="leap_day", name="Leap", birth_date=date(1992, 2, 29),
         birth_time=time(0, 1), birth_place="Mumbai", lat=19.0760, lon=72.8777,
         tz="Asia/Kolkata"),

    # Just past midnight — checks date boundary handling
    dict(id="just_past_midnight", name="Y2K", birth_date=date(2000, 1, 1),
         birth_time=time(0, 1), birth_place="Tokyo", lat=35.6762, lon=139.6503,
         tz="Asia/Tokyo"),

    # Near end of day — checks time close to midnight
    dict(id="near_midnight", name="Night", birth_date=date(1969, 7, 20),
         birth_time=time(23, 58), birth_place="Houston", lat=29.7604, lon=-95.3698,
         tz="America/Chicago"),
]


# ── Invariant helpers (run against any chart/dasha/yoga triple) ───────────────

def _check_chart(chart, fid):
    """Assert all chart structural invariants. fid is fixture id for error messages."""
    p = f"[{fid}]"

    for planet in Planet:
        assert planet.value in chart.planets, f"{p} Missing planet: {planet.value}"

    assert len(chart.houses) == 12, f"{p} Expected 12 houses, got {len(chart.houses)}"
    signs = [h.sign for h in chart.houses.values()]
    assert len(set(signs)) == 12, f"{p} Houses don't cover all 12 signs: {signs}"

    # Sequential whole-sign houses
    for i in range(12):
        expected = SIGN_ORDER[(SIGN_ORDER.index(signs[i]) + 1) % 12]
        assert expected == signs[(i + 1) % 12], f"{p} House sign sequence broken at house {i+1}"

    # Ketu = Rahu + 180°
    rahu = chart.planets[Planet.RAHU.value].abs_degree
    ketu = chart.planets[Planet.KETU.value].abs_degree
    diff = abs(rahu - ketu)
    if diff > 180:
        diff = 360 - diff
    assert abs(diff - 180) < 0.01, f"{p} Rahu-Ketu diff {diff:.3f}° ≠ 180°"

    for name, pos in chart.planets.items():
        assert 0 <= pos.abs_degree < 360,  f"{p} {name} abs_degree out of range: {pos.abs_degree}"
        assert 0 <= pos.degree < 30,       f"{p} {name} sign-degree out of range: {pos.degree}"
        assert 1 <= pos.house <= 12,       f"{p} {name} house out of range: {pos.house}"
        assert 1 <= pos.nakshatra_pada <= 4, f"{p} {name} pada out of range: {pos.nakshatra_pada}"

        # House number must be consistent with sign placement relative to lagna
        lagna_idx = SIGN_ORDER.index(chart.lagna)
        expected_house = (SIGN_ORDER.index(pos.sign) - lagna_idx) % 12 + 1
        assert pos.house == expected_house, (
            f"{p} {name}: sign {pos.sign} → expected house {expected_house}, got {pos.house}"
        )


def _check_dasha(dasha, fid):
    p = f"[{fid}]"

    assert dasha.current_mahadasha is not None, f"{p} No current mahadasha"
    assert dasha.current_antardasha is not None, f"{p} No current antardasha"
    assert len(dasha.mahadashas) == 9, f"{p} Expected 9 mahadashas, got {len(dasha.mahadashas)}"

    total_days = sum((m.end_date - m.start_date).days for m in dasha.mahadashas)
    assert total_days <= 120 * 365.25 + 2, f"{p} Total dasha exceeds 120 years: {total_days} days"
    assert total_days > 0, f"{p} Zero total dasha duration"

    sorted_maha = sorted(dasha.mahadashas, key=lambda m: m.start_date)
    for i in range(len(sorted_maha) - 1):
        assert sorted_maha[i].end_date == sorted_maha[i + 1].start_date, (
            f"{p} Gap/overlap between mahadasha {i} and {i+1}"
        )

    for maha in dasha.mahadashas:
        sub = sorted(maha.sub_dashas, key=lambda a: a.start_date)
        total = sum((a.end_date - a.start_date).days for a in sub)
        expected = (maha.end_date - maha.start_date).days
        assert abs(total - expected) <= 5, (
            f"{p} {maha.planet} antardasha sum {total} ≠ {expected} days"
        )
        for i in range(len(sub) - 1):
            assert sub[i].end_date == sub[i + 1].start_date, (
                f"{p} Gap in {maha.planet} antardashas at period {i}"
            )


def _check_yogas(yogas, fid):
    p = f"[{fid}]"
    assert isinstance(yogas, list) and len(yogas) > 0, f"{p} Empty yoga list"
    valid = {YogaConfidence.CONFIRMED, YogaConfidence.BORDERLINE, YogaConfidence.NOT_FORMED}
    for y in yogas:
        assert y.confidence in valid, f"{p} Invalid confidence: {y.confidence}"
        assert y.name, f"{p} Yoga missing name"
        assert y.formation_details, f"{p} Yoga missing formation_details"
        assert isinstance(y.planets_involved, list), f"{p} planets_involved not a list"
    filtered = filter_yogas(yogas)
    assert all(y.confidence != YogaConfidence.NOT_FORMED for y in filtered), (
        f"{p} filter_yogas left not_formed yogas in result"
    )


def test_invariants_across_all_fixtures():
    """Run all structural invariants against every fixture. Accumulates all failures."""
    failures = []
    for fx in PARAM_FIXTURES:
        fid = fx["id"]
        try:
            chart = generate_birth_chart(
                name=fx["name"],
                birth_date=fx["birth_date"],
                birth_time=fx["birth_time"],
                birth_place=fx["birth_place"],
                latitude=fx["lat"],
                longitude=fx["lon"],
                timezone=fx["tz"],
            )
            dasha = calculate_dasha(chart)
            yogas = scan_yogas(chart)
            _check_chart(chart, fid)
            _check_dasha(dasha, fid)
            _check_yogas(yogas, fid)
            print(f"  ok    {fid}")
        except Exception as e:
            failures.append(f"  FAIL  {fid}: {e}")
            print(failures[-1])

    assert not failures, f"\n{len(failures)} fixture(s) failed:\n" + "\n".join(failures)


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
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
    sys.exit(1 if failed else 0)
