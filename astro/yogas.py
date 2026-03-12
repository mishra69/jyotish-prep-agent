"""
Yoga scanner — checks a birth chart for major Jyotish yogas.
Returns confirmed, borderline (triggers ask_human), or not formed.
"""
from __future__ import annotations

from .models import (
    Planet, Sign, YogaConfidence, YogaResult, BirthChart,
    SIGN_ORDER, SIGN_LORDS, house_whole_sign,
)

KENDRAS = {1, 4, 7, 10}
TRIKONAS = {1, 5, 9}
DUSTHANAS = {6, 8, 12}
UPACHAYAS = {3, 6, 10, 11}

EXALTATION: dict[Planet, Sign] = {
    Planet.SUN:     Sign.ARIES,
    Planet.MOON:    Sign.TAURUS,
    Planet.MARS:    Sign.CAPRICORN,
    Planet.MERCURY: Sign.VIRGO,
    Planet.JUPITER: Sign.CANCER,
    Planet.VENUS:   Sign.PISCES,
    Planet.SATURN:  Sign.LIBRA,
    Planet.RAHU:    Sign.GEMINI,
    Planet.KETU:    Sign.SAGITTARIUS,
}

DEBILITATION: dict[Planet, Sign] = {
    Planet.SUN:     Sign.LIBRA,
    Planet.MOON:    Sign.SCORPIO,
    Planet.MARS:    Sign.CANCER,
    Planet.MERCURY: Sign.PISCES,
    Planet.JUPITER: Sign.CAPRICORN,
    Planet.VENUS:   Sign.VIRGO,
    Planet.SATURN:  Sign.ARIES,
    Planet.RAHU:    Sign.SAGITTARIUS,
    Planet.KETU:    Sign.GEMINI,
}

OWN_SIGNS: dict[Planet, list[Sign]] = {
    Planet.SUN:     [Sign.LEO],
    Planet.MOON:    [Sign.CANCER],
    Planet.MARS:    [Sign.ARIES, Sign.SCORPIO],
    Planet.MERCURY: [Sign.GEMINI, Sign.VIRGO],
    Planet.JUPITER: [Sign.SAGITTARIUS, Sign.PISCES],
    Planet.VENUS:   [Sign.TAURUS, Sign.LIBRA],
    Planet.SATURN:  [Sign.CAPRICORN, Sign.AQUARIUS],
}

NATURAL_BENEFICS = {Planet.JUPITER, Planet.VENUS, Planet.MERCURY, Planet.MOON}
NATURAL_MALEFICS = {Planet.SUN, Planet.MARS, Planet.SATURN, Planet.RAHU, Planet.KETU}


def _house(chart: BirthChart, planet: Planet) -> int:
    return chart.planets[planet.value].house


def _sign(chart: BirthChart, planet: Planet) -> Sign:
    return chart.planets[planet.value].sign


def _same_sign(chart: BirthChart, p1: Planet, p2: Planet) -> bool:
    return _sign(chart, p1) == _sign(chart, p2)


def _house_lord(chart: BirthChart, house_num: int) -> Planet:
    return chart.houses[house_num].lord


def _is_exalted(planet: Planet, sign: Sign) -> bool:
    return EXALTATION.get(planet) == sign


def _is_debilitated(planet: Planet, sign: Sign) -> bool:
    return DEBILITATION.get(planet) == sign


def _is_own_sign(planet: Planet, sign: Sign) -> bool:
    return sign in OWN_SIGNS.get(planet, [])


def _house_from_moon(chart: BirthChart, planet: Planet) -> int:
    moon_sign = _sign(chart, Planet.MOON)
    planet_sign = _sign(chart, planet)
    return house_whole_sign(planet_sign, moon_sign)


# ──────────────────────────────────────────────────────────────────────────────
# Individual yoga checkers
# ──────────────────────────────────────────────────────────────────────────────

def _gajakesari(chart: BirthChart) -> YogaResult:
    """Jupiter in kendra (1,4,7,10) from Moon."""
    jup_from_moon = _house_from_moon(chart, Planet.JUPITER)
    formed = jup_from_moon in KENDRAS

    if formed:
        conf = YogaConfidence.CONFIRMED
        details = (
            f"Jupiter is in house {jup_from_moon} from Moon "
            f"(Moon in {_sign(chart, Planet.MOON).value}, "
            f"Jupiter in {_sign(chart, Planet.JUPITER).value})."
        )
    else:
        conf = YogaConfidence.NOT_FORMED
        details = (
            f"Jupiter is in house {jup_from_moon} from Moon — "
            f"not a kendra. Yoga not formed."
        )

    return YogaResult(
        name="Gajakesari Yoga",
        sanskrit_name="गजकेसरी योग",
        confidence=conf,
        planets_involved=[Planet.JUPITER.value, Planet.MOON.value],
        description="Jupiter in an angular house from Moon — reputation, wisdom, good fortune.",
        formation_details=details,
    )


def _budhaditya(chart: BirthChart) -> YogaResult:
    """Sun and Mercury in the same sign."""
    formed = _same_sign(chart, Planet.SUN, Planet.MERCURY)
    sign = _sign(chart, Planet.SUN)

    if formed:
        # Borderline if Mercury is within 3° of Sun (very combust — debated in Jyotish)
        sun_deg = chart.planets[Planet.SUN.value].abs_degree
        mer_deg = chart.planets[Planet.MERCURY.value].abs_degree
        separation = abs(sun_deg - mer_deg)
        if separation > 180:
            separation = 360 - separation
        if separation <= 3.0:
            conf = YogaConfidence.BORDERLINE
            details = (
                f"Sun and Mercury conjunct in {sign.value} but only {separation:.1f}° apart "
                f"(Mercury very combust). Classical texts differ on whether the yoga holds."
            )
        else:
            conf = YogaConfidence.CONFIRMED
            details = f"Sun and Mercury both in {sign.value}, {separation:.1f}° apart."
    else:
        conf = YogaConfidence.NOT_FORMED
        details = (
            f"Sun in {_sign(chart, Planet.SUN).value}, "
            f"Mercury in {_sign(chart, Planet.MERCURY).value} — different signs."
        )

    return YogaResult(
        name="Budhaditya Yoga",
        sanskrit_name="बुधादित्य योग",
        confidence=conf,
        planets_involved=[Planet.SUN.value, Planet.MERCURY.value],
        description="Sun and Mercury conjunct — intelligence, analytical talent, communication skills.",
        formation_details=details,
    )


def _chandra_mangala(chart: BirthChart) -> YogaResult:
    """Moon and Mars in the same sign."""
    formed = _same_sign(chart, Planet.MOON, Planet.MARS)
    if formed:
        conf = YogaConfidence.CONFIRMED
        details = f"Moon and Mars both in {_sign(chart, Planet.MOON).value}."
    else:
        conf = YogaConfidence.NOT_FORMED
        details = (
            f"Moon in {_sign(chart, Planet.MOON).value}, "
            f"Mars in {_sign(chart, Planet.MARS).value}."
        )
    return YogaResult(
        name="Chandra-Mangala Yoga",
        sanskrit_name="चंद्र-मंगल योग",
        confidence=conf,
        planets_involved=[Planet.MOON.value, Planet.MARS.value],
        description="Moon and Mars conjunct — drive, financial acumen, dynamic emotions.",
        formation_details=details,
    )


def _pancha_mahapurusha(chart: BirthChart) -> list[YogaResult]:
    """
    Five Mahapurusha yogas: Mars/Mercury/Jupiter/Venus/Saturn
    in own sign or exaltation AND in a kendra (1,4,7,10).
    """
    specs = [
        (Planet.MARS,    "Ruchaka", "रुचक",    "Mars",    "courage, authority, physical vitality"),
        (Planet.MERCURY, "Bhadra",  "भद्र",    "Mercury", "intellect, communication, business acumen"),
        (Planet.JUPITER, "Hamsa",   "हंस",     "Jupiter", "wisdom, spirituality, prosperity"),
        (Planet.VENUS,   "Malavya", "मालव्य",  "Venus",   "beauty, luxury, artistic talent"),
        (Planet.SATURN,  "Shasha",  "शश",      "Saturn",  "discipline, longevity, leadership"),
    ]
    results = []
    for planet, name, skt, planet_name, desc in specs:
        sign = _sign(chart, planet)
        house = _house(chart, planet)
        in_kendra = house in KENDRAS
        in_own = _is_own_sign(planet, sign)
        in_exalt = _is_exalted(planet, sign)

        if (in_own or in_exalt) and in_kendra:
            strength = "own sign" if in_own else "exaltation"
            conf = YogaConfidence.CONFIRMED
            details = f"{planet_name} in {strength} ({sign.value}) in house {house} (kendra)."
        elif (in_own or in_exalt) and not in_kendra:
            conf = YogaConfidence.BORDERLINE
            strength = "own sign" if in_own else "exaltation"
            details = (
                f"{planet_name} is in {strength} ({sign.value}) but in house {house} "
                f"(not a kendra — classical texts require kendra placement)."
            )
        elif in_kendra and not (in_own or in_exalt):
            conf = YogaConfidence.NOT_FORMED
            details = f"{planet_name} in kendra (house {house}) but not in own sign or exaltation."
        else:
            conf = YogaConfidence.NOT_FORMED
            details = f"{planet_name} in house {house} ({sign.value}) — neither kendra nor own/exalted."

        results.append(YogaResult(
            name=f"{name} Yoga (Pancha Mahapurusha)",
            sanskrit_name=f"{skt} योग",
            confidence=conf,
            planets_involved=[planet.value],
            description=f"{name} Yoga — {desc}.",
            formation_details=details,
        ))
    return results


def _neechabhanga_raja_yoga(chart: BirthChart) -> list[YogaResult]:
    """
    Neechabhanga Raja Yoga: debilitated planet gets cancellation.
    Multiple cancellation conditions — borderline cases flagged for human review.
    """
    results = []
    cancellation_planets = [p for p in Planet if p not in (Planet.RAHU, Planet.KETU)]

    for planet in cancellation_planets:
        sign = _sign(chart, planet)
        if not _is_debilitated(planet, sign):
            continue

        cancellations_met: list[str] = []
        cancellations_partial: list[str] = []

        # Condition 1: Lord of debilitation sign is in kendra from lagna or Moon
        deb_sign_lord = SIGN_LORDS[sign]
        lord_house_lagna = _house(chart, deb_sign_lord)
        lord_house_moon = _house_from_moon(chart, deb_sign_lord)
        if lord_house_lagna in KENDRAS:
            cancellations_met.append(
                f"Lord of debilitation sign ({deb_sign_lord.value}) is in kendra from lagna (house {lord_house_lagna})"
            )
        elif lord_house_moon in KENDRAS:
            cancellations_met.append(
                f"Lord of debilitation sign ({deb_sign_lord.value}) is in kendra from Moon (house {lord_house_moon})"
            )

        # Condition 2: Planet that exalts in the debilitation sign is in kendra
        exalt_planet = next((p for p, s in EXALTATION.items() if s == sign), None)
        if exalt_planet:
            ep_house = _house(chart, exalt_planet)
            if ep_house in KENDRAS:
                cancellations_met.append(
                    f"Planet exalted in {sign.value} ({exalt_planet.value}) is in kendra (house {ep_house})"
                )

        # Condition 3: Debilitated planet in own navamsha (simplified: check if nearly exalted)
        planet_deg = chart.planets[planet.value].abs_degree
        exalt_sign = EXALTATION.get(planet)
        if exalt_sign:
            exalt_sign_idx = SIGN_ORDER.index(exalt_sign)
            exalt_abs_start = exalt_sign_idx * 30.0
            if abs(planet_deg - exalt_abs_start) <= 5.0 or abs(planet_deg - (exalt_abs_start + 30)) <= 5.0:
                cancellations_partial.append(
                    f"{planet.value} is close to its exaltation sign boundary — partial cancellation possible"
                )

        if not cancellations_met and not cancellations_partial:
            continue  # Debilitated but no cancellation — skip (not a yoga)

        if cancellations_met:
            conf = YogaConfidence.CONFIRMED if len(cancellations_met) >= 2 else YogaConfidence.BORDERLINE
            details = (
                f"{planet.value} debilitated in {sign.value}. "
                f"Cancellation conditions met: {'; '.join(cancellations_met)}."
            )
            if len(cancellations_met) == 1:
                details += " Only one condition met — borderline. Verify strength."
        else:
            conf = YogaConfidence.BORDERLINE
            details = (
                f"{planet.value} debilitated in {sign.value}. "
                f"Partial cancellation: {'; '.join(cancellations_partial)}. Needs astrologer assessment."
            )

        results.append(YogaResult(
            name=f"Neechabhanga Raja Yoga ({planet.value})",
            sanskrit_name="नीचभंग राज योग",
            confidence=conf,
            planets_involved=[planet.value],
            description="Debilitation cancelled, turning weakness into strength and Raja Yoga.",
            formation_details=details,
        ))
    return results


def _raja_yoga(chart: BirthChart) -> list[YogaResult]:
    """
    Basic Raja Yoga: lord of a kendra conjunct lord of a trikona.
    Checks all kendra-trikona lord pairs in the same sign.
    """
    results = []
    kendra_lords = {h: _house_lord(chart, h) for h in KENDRAS}
    trikona_lords = {h: _house_lord(chart, h) for h in TRIKONAS}

    seen_pairs: set[frozenset] = set()

    for kh, kl in kendra_lords.items():
        for th, tl in trikona_lords.items():
            if kl == tl:
                continue  # Same planet — natural yoga, less notable
            pair = frozenset([kl, tl])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if _same_sign(chart, kl, tl):
                conf = YogaConfidence.CONFIRMED
                details = (
                    f"Lord of house {kh} ({kl.value}) conjunct lord of house {th} ({tl.value}) "
                    f"in {_sign(chart, kl).value}."
                )
                results.append(YogaResult(
                    name=f"Raja Yoga ({kl.value}–{tl.value})",
                    sanskrit_name="राज योग",
                    confidence=conf,
                    planets_involved=[kl.value, tl.value],
                    description=f"Kendra lord ({kl.value}) and trikona lord ({tl.value}) conjunct — power, status, authority.",
                    formation_details=details,
                ))

    return results


def _viparita_raja_yoga(chart: BirthChart) -> list[YogaResult]:
    """
    Viparita Raja Yoga: lords of 6, 8, 12 in each other's houses or conjunct.
    Harsha (6th lord in 8th/12th), Sarala (8th lord in 6th/12th), Vimala (12th lord in 6th/8th).
    """
    results = []
    dusthana_pairs = [
        (6, "Harsha", "हर्ष", "Strength through obstacles, victory over enemies"),
        (8, "Sarala", "सरल", "Courage, longevity, freedom from fear"),
        (12, "Vimala", "विमल", "Purity, moksha, liberation from debt"),
    ]

    for house_num, name, skt, desc in dusthana_pairs:
        lord = _house_lord(chart, house_num)
        lord_house = _house(chart, lord)

        other_dusthanas = DUSTHANAS - {house_num}
        if lord_house in other_dusthanas:
            conf = YogaConfidence.CONFIRMED
            details = (
                f"Lord of house {house_num} ({lord.value}) is in house {lord_house} "
                f"(a dusthana) — {name} Viparita Raja Yoga formed."
            )
            results.append(YogaResult(
                name=f"{name} Viparita Raja Yoga",
                sanskrit_name=f"{skt} विपरीत राज योग",
                confidence=conf,
                planets_involved=[lord.value],
                description=f"{name} Viparita Raja Yoga — {desc}.",
                formation_details=details,
            ))
        elif lord_house == house_num:
            conf = YogaConfidence.BORDERLINE
            details = (
                f"Lord of house {house_num} ({lord.value}) is in its own dusthana (house {lord_house}). "
                f"Partial {name} yoga — some astrologers accept this, others require placement in a different dusthana."
            )
            results.append(YogaResult(
                name=f"{name} Viparita Raja Yoga (partial)",
                sanskrit_name=f"{skt} विपरीत राज योग",
                confidence=conf,
                planets_involved=[lord.value],
                description=f"{name} Viparita Raja Yoga — {desc}.",
                formation_details=details,
            ))

    return results


def _dhana_yoga(chart: BirthChart) -> YogaResult:
    """Lord of 2nd and lord of 11th conjunct, or in mutual houses."""
    l2 = _house_lord(chart, 2)
    l11 = _house_lord(chart, 11)

    if l2 == l11:
        conf = YogaConfidence.CONFIRMED
        details = f"Same planet ({l2.value}) rules both 2nd and 11th houses — strong Dhana Yoga."
    elif _same_sign(chart, l2, l11):
        conf = YogaConfidence.CONFIRMED
        sign = _sign(chart, l2)
        details = f"Lord of 2nd ({l2.value}) and lord of 11th ({l11.value}) conjunct in {sign.value}."
    elif _house(chart, l2) == 11 or _house(chart, l11) == 2:
        conf = YogaConfidence.CONFIRMED
        details = (
            f"Mutual house exchange: 2nd lord ({l2.value}) in house {_house(chart, l2)}, "
            f"11th lord ({l11.value}) in house {_house(chart, l11)}."
        )
    else:
        conf = YogaConfidence.NOT_FORMED
        details = (
            f"2nd lord ({l2.value}) in house {_house(chart, l2)}, "
            f"11th lord ({l11.value}) in house {_house(chart, l11)} — no connection."
        )

    return YogaResult(
        name="Dhana Yoga",
        sanskrit_name="धन योग",
        confidence=conf,
        planets_involved=[l2.value, l11.value],
        description="Wealth yoga — lords of 2nd (accumulated wealth) and 11th (income) connected.",
        formation_details=details,
    )


def _adhi_yoga(chart: BirthChart) -> YogaResult:
    """Natural benefics (Jupiter, Venus, Mercury) in 6th, 7th, 8th from Moon."""
    benefics_in_678 = []
    for planet in [Planet.JUPITER, Planet.VENUS, Planet.MERCURY]:
        h = _house_from_moon(chart, planet)
        if h in {6, 7, 8}:
            benefics_in_678.append((planet, h))

    if len(benefics_in_678) == 3:
        conf = YogaConfidence.CONFIRMED
        detail_parts = [f"{p.value} in house {h} from Moon" for p, h in benefics_in_678]
        details = "All three natural benefics in 6th/7th/8th from Moon: " + ", ".join(detail_parts) + "."
    elif len(benefics_in_678) == 2:
        conf = YogaConfidence.BORDERLINE
        detail_parts = [f"{p.value} in house {h} from Moon" for p, h in benefics_in_678]
        details = (
            f"Two of three benefics in 6th/7th/8th from Moon: {', '.join(detail_parts)}. "
            f"Classical definition requires all three — partial yoga."
        )
    else:
        conf = YogaConfidence.NOT_FORMED
        details = f"Fewer than two natural benefics in 6th/7th/8th from Moon."

    return YogaResult(
        name="Adhi Yoga",
        sanskrit_name="आधि योग",
        confidence=conf,
        planets_involved=[Planet.JUPITER.value, Planet.VENUS.value, Planet.MERCURY.value],
        description="Natural benefics in angular positions from Moon — leadership, comfort, respected position.",
        formation_details=details,
    )


def _kemadruma(chart: BirthChart) -> YogaResult:
    """
    Kemadruma Yoga: No planets in 2nd or 12th from Moon (and Moon not in kendra with planets).
    This is an inauspicious yoga — loneliness, hardship.
    """
    moon_sign_idx = SIGN_ORDER.index(_sign(chart, Planet.MOON))
    sign_2nd = SIGN_ORDER[(moon_sign_idx + 1) % 12]
    sign_12th = SIGN_ORDER[(moon_sign_idx - 1) % 12]

    planets_near_moon = []
    for planet in Planet:
        if planet in (Planet.MOON, Planet.RAHU, Planet.KETU, Planet.SUN):
            continue  # Sun, Rahu, Ketu don't cancel Kemadruma classically
        psign = _sign(chart, planet)
        if psign in (sign_2nd, sign_12th):
            planets_near_moon.append(planet)

    # Also check if any planet in kendra from lagna is the same as Moon's kendra position
    moon_in_kendra = _house(chart, Planet.MOON) in KENDRAS

    if not planets_near_moon:
        if moon_in_kendra:
            conf = YogaConfidence.BORDERLINE
            details = (
                "No planets in 2nd or 12th from Moon, but Moon is in a kendra — "
                "some texts say this cancels Kemadruma."
            )
        else:
            conf = YogaConfidence.CONFIRMED
            details = "No planets in 2nd or 12th from Moon. Kemadruma Yoga present."
    else:
        conf = YogaConfidence.NOT_FORMED
        planets_str = ", ".join(p.value for p in planets_near_moon)
        details = f"Kemadruma cancelled by {planets_str} in the adjacent signs."

    return YogaResult(
        name="Kemadruma Yoga",
        sanskrit_name="केमद्रुम योग",
        confidence=conf,
        planets_involved=[Planet.MOON.value],
        description="Moon isolated — potential for hardship, emotional difficulty, lack of support.",
        formation_details=details,
    )


def _saraswati_yoga(chart: BirthChart) -> YogaResult:
    """Jupiter, Venus, Mercury all in kendras or trikonas."""
    results = {}
    for planet in [Planet.JUPITER, Planet.VENUS, Planet.MERCURY]:
        h = _house(chart, planet)
        results[planet] = h

    in_kendra_trikona = {p: h for p, h in results.items() if h in (KENDRAS | TRIKONAS)}

    if len(in_kendra_trikona) == 3:
        conf = YogaConfidence.CONFIRMED
        detail_parts = [f"{p.value} in house {h}" for p, h in in_kendra_trikona.items()]
        details = "Jupiter, Venus, Mercury all in kendras/trikonas: " + ", ".join(detail_parts) + "."
    elif len(in_kendra_trikona) == 2:
        conf = YogaConfidence.BORDERLINE
        detail_parts = [f"{p.value} in house {h}" for p, h in in_kendra_trikona.items()]
        missing = [p for p in [Planet.JUPITER, Planet.VENUS, Planet.MERCURY] if p not in in_kendra_trikona]
        details = (
            f"Two of three in kendras/trikonas: {', '.join(detail_parts)}. "
            f"{missing[0].value} is in house {results[missing[0]]} — partial yoga."
        )
    else:
        conf = YogaConfidence.NOT_FORMED
        details = "Jupiter, Venus, Mercury not sufficiently placed in kendras or trikonas."

    return YogaResult(
        name="Saraswati Yoga",
        sanskrit_name="सरस्वती योग",
        confidence=conf,
        planets_involved=[Planet.JUPITER.value, Planet.VENUS.value, Planet.MERCURY.value],
        description="Wisdom, learning, creative intelligence — all three knowledge planets strong.",
        formation_details=details,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main scanner
# ──────────────────────────────────────────────────────────────────────────────

def scan_yogas(chart: BirthChart) -> list[YogaResult]:
    """
    Scan a birth chart for all implemented yogas.
    Returns all results (confirmed + borderline + not_formed).
    Borderline results are candidates for the ask_human tool.
    """
    results: list[YogaResult] = []

    results.append(_gajakesari(chart))
    results.append(_budhaditya(chart))
    results.append(_chandra_mangala(chart))
    results.extend(_pancha_mahapurusha(chart))
    results.extend(_neechabhanga_raja_yoga(chart))
    results.extend(_raja_yoga(chart))
    results.extend(_viparita_raja_yoga(chart))
    results.append(_dhana_yoga(chart))
    results.append(_adhi_yoga(chart))
    results.append(_kemadruma(chart))
    results.append(_saraswati_yoga(chart))

    return results


def filter_yogas(
    yogas: list[YogaResult],
    include_not_formed: bool = False,
) -> list[YogaResult]:
    """Filter yoga results. By default returns confirmed + borderline only."""
    if include_not_formed:
        return yogas
    return [y for y in yogas if y.confidence != YogaConfidence.NOT_FORMED]
