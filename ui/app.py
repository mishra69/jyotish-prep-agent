"""
Jyotish Prep Agent — Streamlit UI
Single-file app managing all 5 screens via session_state stage machine.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

# Make project root importable when run as `streamlit run ui/app.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from astro.models import NAKSHATRAS, SIGN_LORDS
from astro.yogas import EXALTATION, DEBILITATION, OWN_SIGNS, NATURAL_BENEFICS, NATURAL_MALEFICS
from astro.dasha import NAKSHATRA_LORDS

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Jyotish Prep Agent",
    page_icon="🪐",
    layout="wide",
)

# ── Graph (cached across reruns) ──────────────────────────────────────────────

@st.cache_resource
def get_graph():
    from agent.graph import build_graph
    return build_graph(os.path.join(os.path.dirname(__file__), "..", "jyotish.db"))

# ── Session state init ────────────────────────────────────────────────────────

def _init():
    defaults = {
        "stage": "intake",
        "thread_id": None,
        "interrupt_data": None,
        "final_brief": None,
        "error": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


def _restore_from_url():
    """Restore session from ?t= query param (survives hard refresh / network switch)."""
    t = st.query_params.get("t")
    if not t or st.session_state.thread_id:
        return  # Nothing to restore, or session already active

    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": t}}
        graph_state = graph.get_state(config)

        if not graph_state or not graph_state.values:
            return  # Thread not found in DB

        st.session_state.thread_id = t

        # Look for a pending interrupt
        idata = None
        for task in (graph_state.tasks or []):
            for intr in (getattr(task, "interrupts", None) or []):
                idata = intr.value if hasattr(intr, "value") else intr
                break
            if idata:
                break

        if idata:
            itype = idata.get("type") if isinstance(idata, dict) else ""
            st.session_state.interrupt_data = idata
            st.session_state.stage = {
                "checkpoint_1": "checkpoint_1",
                "ask_human": "ask_human",
                "checkpoint_2": "checkpoint_2",
            }.get(itype, "error")
        elif not graph_state.next:
            # Graph ran to completion
            st.session_state.stage = "done"
            st.session_state.final_brief = (graph_state.values or {}).get("draft_brief", "")
        # else: graph mid-run (shouldn't happen) — leave as intake

    except Exception:
        pass  # Silently fall through to intake


_restore_from_url()

# ── Graph helpers ─────────────────────────────────────────────────────────────

def _advance(input_data):
    """
    Run the graph until the next interrupt or completion.
    Updates st.session_state.stage and interrupt_data.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    st.session_state.error = None

    try:
        for chunk in graph.stream(input_data, config=config, stream_mode="updates"):
            for node_name, updates in chunk.items():
                if node_name == "__interrupt__":
                    interrupts = updates
                    if not interrupts:
                        continue
                    idata = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
                    st.session_state.interrupt_data = idata
                    itype = idata.get("type") if isinstance(idata, dict) else ""
                    st.session_state.stage = {
                        "checkpoint_1": "checkpoint_1",
                        "ask_human": "ask_human",
                        "checkpoint_2": "checkpoint_2",
                    }.get(itype, "error")
                    return

        # Graph ran to completion
        graph_state = graph.get_state(config)
        final = (graph_state.values or {}).get("draft_brief", "")
        st.session_state.final_brief = final
        st.session_state.stage = "done"

    except Exception as e:
        st.session_state.error = str(e)
        st.session_state.stage = "error"


def start_graph(initial_state: dict):
    st.session_state.thread_id = str(uuid.uuid4())
    _advance(initial_state)


def resume_graph(response):
    _advance(Command(resume=response))

# ── UI helpers ────────────────────────────────────────────────────────────────

STAGE_LABELS = {
    "intake": "1 · Intake",
    "checkpoint_1": "2 · Prep Review",
    "ask_human": "3 · Agent Question",
    "checkpoint_2": "4 · Draft Review",
    "done": "5 · Final Brief",
}

CONFIDENCE_ICON = {
    "confirmed": "✦",
    "borderline": "⚠",
    "not_formed": "✗",
}
CONFIDENCE_COLOR = {
    "confirmed": "green",
    "borderline": "orange",
    "not_formed": "gray",
}

# ── Planetary table lookup data (derived from astro modules) ──────────────────

_PLANET_ABBR = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke",
}
_NAK_LORD_ABBR: dict[str, str] = {
    nak: _PLANET_ABBR[lord.value] for nak, lord in zip(NAKSHATRAS, NAKSHATRA_LORDS)
}
_EXALT: dict[str, str]   = {p.value: s.value for p, s in EXALTATION.items()}
_DEBIT: dict[str, str]   = {p.value: s.value for p, s in DEBILITATION.items()}
_OWN: dict[str, set]     = {p.value: {s.value for s in signs} for p, signs in OWN_SIGNS.items()}
_SIGN_LORD: dict[str, str] = {s.value: p.value for s, p in SIGN_LORDS.items()}
_MALEFICS_SET: set[str]  = {p.value for p in NATURAL_MALEFICS}
_BENEFICS_SET: set[str]  = {p.value for p in NATURAL_BENEFICS}

# No corresponding source in astro modules — kept here
_DIG_BALA: dict[str, int] = {
    "Sun": 10, "Mars": 10, "Jupiter": 1, "Mercury": 1,
    "Moon": 4, "Venus": 4, "Saturn": 7,
}
_COMBUST_ORB: dict[str, float] = {
    "Mars": 17.0, "Mercury": 14.0, "Jupiter": 11.0,
    "Venus": 10.0, "Saturn": 15.0,
}
_FRIENDS: dict[str, set] = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
    "Rahu": {"Saturn", "Venus", "Mercury"},
    "Ketu": {"Saturn", "Venus", "Mercury"},
}
_ENEMIES: dict[str, set] = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
    "Rahu": {"Sun", "Moon", "Mars"},
    "Ketu": {"Sun", "Moon", "Mars"},
}
_SPECIAL_ASPECTS: dict[str, set] = {
    "Mars": {4, 8}, "Jupiter": {5, 9}, "Saturn": {3, 10},
}
_PLANET_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

# If True, combustion suppresses retrograde strength (classical view: Sun overwhelms vakri energy).
# If False, both Retro and Comb appear independently.
COMBUST_SUPPRESSES_RETRO = True

def _sidebar():
    st.sidebar.title("🪐 Jyotish Prep")
    current = st.session_state.stage
    stage_keys = list(STAGE_LABELS.keys())
    current_idx = stage_keys.index(current) if current in stage_keys else -1
    for i, (key, label) in enumerate(STAGE_LABELS.items()):
        if key == current:
            st.sidebar.markdown(f"**→ {label}**")
        elif current_idx == -1 or i < current_idx:
            st.sidebar.markdown(f"~~{label}~~")
        else:
            st.sidebar.markdown(f"{label}")

    if st.session_state.thread_id:
        st.sidebar.caption(f"Session: `{st.session_state.thread_id[:8]}…`")

    if st.sidebar.button("↺  New Consultation", use_container_width=True):
        clear_none = ["thread_id", "interrupt_data", "final_brief", "error",
                      "location_candidates", "location_selected"]
        clear_empty = ["intake_name", "intake_custom_topic", "intake_client_questions",
                       "intake_location_query"]
        for k in clear_none:
            st.session_state[k] = None
        for k in clear_empty:
            st.session_state[k] = ""
        st.session_state["stage"] = "intake"
        st.query_params.clear()
        st.rerun()


def _planet_table(chart: dict) -> None:
    planets = chart.get("planets", {})
    houses = chart.get("houses", {})

    sun_abs = planets.get("Sun", {}).get("abs_degree", 0.0)
    moon_abs = planets.get("Moon", {}).get("abs_degree", 0.0)
    moon_sun_sep = abs(moon_abs - sun_abs)
    if moon_sun_sep > 180:
        moon_sun_sep = 360 - moon_sun_sep

    # planet name → list of house numbers it lords
    lorded_by: dict[str, list] = {}
    for h_str, hdata in houses.items():
        lord = hdata.get("lord", "")
        lorded_by.setdefault(lord, []).append(int(h_str))

    # planet name → house number
    planet_house: dict[str, int] = {p: d.get("house", 0) for p, d in planets.items()}

    # house → list of planets aspecting it
    aspected_by: dict[int, list] = {}
    for pname, h in planet_house.items():
        if h == 0:
            continue
        asp = {((h - 1 + 6) % 12) + 1}  # 7th house aspect
        asp |= {((h - 1 + (x - 1)) % 12) + 1 for x in _SPECIAL_ASPECTS.get(pname, set())}
        for ah in asp:
            aspected_by.setdefault(ah, []).append(pname)

    rows = []
    for planet_name in _PLANET_ORDER:
        if planet_name not in planets:
            continue
        pos = planets[planet_name]
        sign = pos.get("sign", "")
        degree = pos.get("degree", 0.0)
        house = pos.get("house", 0)
        nakshatra = pos.get("nakshatra", "")
        retrograde = pos.get("retrograde", False)
        abs_deg = pos.get("abs_degree", 0.0)

        # Nakshatra + lord abbreviation
        nak_lord = _NAK_LORD_ABBR.get(nakshatra, "?")
        nak_str = f"{nakshatra} ({nak_lord})"

        # ── Strengths & Weaknesses ─────────────────────────────────────────────
        strengths: list[str] = []
        weaknesses: list[str] = []

        # Combust check first — it gates retrograde strength
        combust = False
        if planet_name == "Moon":
            if moon_sun_sep >= 170:
                strengths.append("FM")
            elif moon_sun_sep <= 10:
                weaknesses.append("NM")
        elif planet_name not in ("Sun", "Rahu", "Ketu"):
            orb = _COMBUST_ORB.get(planet_name, 0.0)
            sep = abs(abs_deg - sun_abs)
            if sep > 180:
                sep = 360 - sep
            if sep <= orb:
                combust = True
                weaknesses.append("Comb")

        if _EXALT.get(planet_name) == sign:
            strengths.append("Exalt")
        if sign in _OWN.get(planet_name, set()):
            strengths.append("Swa")
        if _DIG_BALA.get(planet_name) == house:
            strengths.append("Dig")
        if retrograde and not (combust and COMBUST_SUPPRESSES_RETRO) and planet_name not in ("Rahu", "Ketu"):
            strengths.append("Retro")

        if _DEBIT.get(planet_name) == sign:
            weaknesses.append("Deb")

        # ── Score ──────────────────────────────────────────────────────────────
        s, w = len(strengths), len(weaknesses)
        net = s - w
        label = "Exagg." if net >= 1 else ("Dimin." if net <= -1 else "Ord.")
        score_str = f"+{s} −{w}  {label}"

        # ── Stabilized / Destabilized ──────────────────────────────────────────
        stabilized: list[str] = []
        destabilized: list[str] = []

        sign_lord = _SIGN_LORD.get(sign, "")
        if sign_lord and sign_lord != planet_name:
            sl_abbr = _PLANET_ABBR[sign_lord]
            if sign_lord in _FRIENDS.get(planet_name, set()):
                stabilized.append(f"Frnd({sl_abbr})")
            elif sign_lord in _ENEMIES.get(planet_name, set()):
                destabilized.append(f"Enmty({sl_abbr})")

        adj = {((house - 2) % 12) + 1, (house % 12) + 1}
        fln_ben = [_PLANET_ABBR[p] for p in _BENEFICS_SET if p != planet_name and planet_house.get(p) in adj]
        fln_mal = [_PLANET_ABBR[p] for p in _MALEFICS_SET if p != planet_name and planet_house.get(p) in adj]
        if fln_ben:
            stabilized.append(f"Fln+({','.join(fln_ben)})")
        if fln_mal:
            destabilized.append(f"Fln−({','.join(fln_mal)})")

        aspectors = aspected_by.get(house, [])
        dri_ben = [_PLANET_ABBR[a] for a in aspectors if a in _BENEFICS_SET and a != planet_name]
        dri_mal = [_PLANET_ABBR[a] for a in aspectors if a in _MALEFICS_SET and a != planet_name]
        if dri_ben:
            stabilized.append(f"Dri+({','.join(dri_ben)})")
        if dri_mal:
            destabilized.append(f"Dri−({','.join(dri_mal)})")

        co_ben = [_PLANET_ABBR[p] for p in _BENEFICS_SET if p != planet_name and planet_house.get(p) == house]
        co_mal = [_PLANET_ABBR[p] for p in _MALEFICS_SET if p != planet_name and planet_house.get(p) == house]
        if co_ben:
            stabilized.append(f"Co+({','.join(co_ben)})")
        if co_mal:
            destabilized.append(f"Co−({','.join(co_mal)})")

        # ── Temporal benefic / malefic ─────────────────────────────────────────
        lorded = lorded_by.get(planet_name, [])
        is_tri = any(h in {1, 5, 9} for h in lorded)
        is_knd = any(h in {1, 4, 7, 10} for h in lorded)
        is_dth = any(h in {6, 8, 12} for h in lorded)

        lordship_parts = []
        if is_tri and is_knd:
            lordship_parts.append("RYK")
        elif is_tri:
            lordship_parts.append("Trikona")
        elif is_knd:
            lordship_parts.append("Kendra")
        if is_dth:
            lordship_parts.append("Dusthana")

        rows.append({
            "Planet": planet_name,
            "Sign": sign,
            "Deg": f"{degree:.1f}°",
            "House": house,
            "Nakshatra": nak_str,
            "Strengths": ", ".join(strengths),
            "Weaknesses": ", ".join(weaknesses),
            "Score": score_str,
            "Stabilized": ", ".join(stabilized),
            "Destabilized": ", ".join(destabilized),
            "Lordship": " · ".join(lordship_parts),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)


def _yoga_list(yogas: list) -> None:
    relevant = [y for y in yogas if y.get("confidence") != "not_formed"]
    if not relevant:
        st.info("No notable yogas found.")
        return
    for yoga in relevant:
        conf = yoga.get("confidence", "")
        icon = CONFIDENCE_ICON.get(conf, "?")
        color = CONFIDENCE_COLOR.get(conf, "gray")
        with st.expander(f":{color}[{icon}] {yoga.get('name')}"):
            st.write(yoga.get("description", ""))
            st.caption(yoga.get("formation_details", ""))

# ── Screen 1: Intake ──────────────────────────────────────────────────────────

TOPICS = ["career", "marriage", "health", "education", "finance", "general"]


def _search_locations(query: str) -> list[dict]:
    """Return up to 5 candidate locations for the query."""
    try:
        from geopy.geocoders import Nominatim
        from timezonefinder import TimezoneFinder
        geolocator = Nominatim(user_agent="jyotish-prep-agent/1.0", timeout=10)
        results = geolocator.geocode(query, language="en", exactly_one=False, limit=5) or []
        tf = TimezoneFinder()
        candidates = []
        for loc in results:
            tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude) or "UTC"
            candidates.append({
                "address": loc.address,
                "lat": loc.latitude,
                "lon": loc.longitude,
                "timezone": tz,
            })
        return candidates
    except Exception:
        return []


def show_intake():
    st.title("New Consultation")
    st.caption("Enter client birth details and the consultation topic.")

    # Without st.form so the location Search button doesn't submit the whole form.
    # Widget values persist in session_state across reruns naturally.

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Client")
        name = st.text_input("Client name (optional)", placeholder="e.g. Priya S.", key="intake_name")
        topics = st.multiselect(
            "Consultation topic(s)",
            TOPICS,
            default=st.session_state.get("intake_topics", ["general"]),
            key="intake_topics",
        )
        custom_topic = st.text_input(
            "Custom / refine topic (optional)",
            placeholder='e.g. "relocation abroad", "job change vs business"',
            key="intake_custom_topic",
        )
        client_questions = st.text_area(
            "Client's specific questions (optional)",
            placeholder="e.g. Will I get a promotion this year?\nIs 2025 good for marriage?",
            height=110,
            key="intake_client_questions",
        )

    with col2:
        st.subheader("Birth details")
        birth_date = st.date_input(
            "Date of birth",
            value=st.session_state.get("intake_birth_date"),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            format="MM/DD/YYYY",
            key="intake_birth_date",
        )
        st.caption("Time of birth")
        tc1, tc2, tc3 = st.columns(3)
        birth_hour = tc1.selectbox(
            "Hour", list(range(1, 13)), index=11,
            label_visibility="collapsed", key="intake_hour",
        )
        birth_minute = tc2.selectbox(
            "Minute", [f"{m:02d}" for m in range(60)], index=0,
            label_visibility="collapsed", key="intake_minute",
        )
        birth_ampm = tc3.selectbox(
            "AM/PM", ["AM", "PM"], index=1,
            label_visibility="collapsed", key="intake_ampm",
        )

        # ── Place of birth with candidate search ──────────────────────────────
        st.write("")
        lc1, lc2 = st.columns([3, 1])
        with lc1:
            location_query = st.text_input(
                "Place of birth",
                placeholder="e.g. Chicago, Illinois, USA",
                key="intake_location_query",
            )
        with lc2:
            st.write("")   # vertical alignment nudge
            search_clicked = st.button("Search", use_container_width=True, key="location_search_btn")

        if search_clicked:
            if not location_query.strip():
                st.warning("Enter a location first.")
            else:
                with st.spinner("Searching…"):
                    candidates = _search_locations(location_query.strip())
                st.session_state.location_candidates = candidates
                st.session_state.location_selected = None

        candidates = st.session_state.get("location_candidates")
        if candidates is not None:
            if len(candidates) == 0:
                st.warning("No locations found — try adding state/country.")
            else:
                labels = [c["address"] for c in candidates]
                chosen = st.radio(
                    "Pick the right location",
                    labels,
                    key="location_radio",
                    label_visibility="collapsed" if len(candidates) == 1 else "visible",
                )
                if chosen:
                    idx = labels.index(chosen)
                    st.session_state.location_selected = candidates[idx]

        loc = st.session_state.get("location_selected")
        if loc:
            st.caption(
                f"Lat {loc['lat']:.4f}, Lon {loc['lon']:.4f}"
                f"  ·  Timezone: **{loc['timezone']}**"
            )

    st.divider()

    submit = st.button("Compute Chart →", type="primary", use_container_width=True)

    if submit:
        loc = st.session_state.get("location_selected")
        errors = []
        if st.session_state.get("intake_birth_date") is None:
            errors.append("Date of birth is required.")
        if not st.session_state.get("intake_topics"):
            errors.append("Select at least one consultation topic.")
        if not loc:
            errors.append("Search and select a birth location.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            hour_24 = birth_hour % 12 + (12 if birth_ampm == "PM" else 0)
            birth_time_str = f"{hour_24:02d}:{birth_minute}"

            initial_state = {
                "client_name": name.strip() or "Client",
                "birth_date": st.session_state["intake_birth_date"].isoformat(),
                "birth_time": birth_time_str,
                "birth_place": loc["address"],
                "latitude": loc["lat"],
                "longitude": loc["lon"],
                "timezone": loc["timezone"],
                "client_topics": st.session_state["intake_topics"],
                "custom_topic": custom_topic.strip(),
                "client_questions": client_questions.strip(),
                "human_answers": [],
                "revision_count": 0,
            }
            _ph = st.empty()
            with _ph:
                with st.spinner("Computing chart, dasha, and yogas…"):
                    start_graph(initial_state)
            _ph.empty()
            st.query_params["t"] = st.session_state.thread_id
            st.rerun()

# ── Screen 2: Checkpoint 1 — Prep Review ─────────────────────────────────────

def show_checkpoint_1():
    idata = st.session_state.interrupt_data or {}
    chart = idata.get("birth_chart", {})
    dasha = idata.get("dasha_data", {})
    yogas = idata.get("yogas", [])

    st.title("Prep Review")
    st.caption("Review the computed chart data. Add corrections or notes before synthesis.")

    # Chart header
    col1, col2, col3 = st.columns(3)
    col1.metric("Lagna", f"{chart.get('lagna')} {chart.get('lagna_degree', 0):.1f}°")
    col2.metric("Moon", f"{chart.get('moon_sign')}")
    col3.metric("Nakshatra", f"{chart.get('moon_nakshatra')} Pada {chart.get('moon_nakshatra_pada')}")

    st.divider()

    tab_planets, tab_dasha, tab_yogas = st.tabs(["Planetary Positions", "Dasha", "Yogas"])

    with tab_planets:
        _planet_table(chart)

    with tab_dasha:
        maha = dasha.get("current_mahadasha", {})
        antar = dasha.get("current_antardasha", {})
        col1, col2 = st.columns(2)
        col1.metric("Mahadasha", maha.get("planet", ""), delta=f"until {maha.get('end_date', '')[:10]}")
        col2.metric("Antardasha", antar.get("planet", ""), delta=f"until {antar.get('end_date', '')[:10]}")

        st.subheader("Upcoming transitions")
        for t in (dasha.get("next_transitions") or []):
            st.write(f"**{t.get('planet')}**  {t.get('start_date','')[:10]} → {t.get('end_date','')[:10]}")

    with tab_yogas:
        _yoga_list(yogas)

    st.divider()

    with st.form("checkpoint_1_form"):
        corrections = st.text_area(
            "Corrections / notes (optional)",
            placeholder="e.g. Birth time is rectified to 14:45. Ignore Kemadruma — cancelled by Moon in kendra.",
            height=100,
        )
        col_a, col_b = st.columns([1, 3])
        approved = col_a.form_submit_button("Approve & Synthesize →", type="primary", use_container_width=True)
        _ = col_b.form_submit_button("Cancel", use_container_width=True)

    if approved:
        _ph = st.empty()
        with _ph:
            with st.spinner("Synthesizing consultation brief… (agent may ask you a question)"):
                resume_graph({"approved": True, "corrections": corrections})
        _ph.empty()
        st.rerun()

# ── Screen 3: Ask Human ───────────────────────────────────────────────────────

def show_ask_human():
    idata = st.session_state.interrupt_data or {}
    question = idata.get("question", "The agent has a question.")

    st.title("Agent Question")
    st.info(
        "The agent encountered an ambiguous pattern and is asking for your expert input "
        "before continuing synthesis."
    )

    st.subheader("Agent's question:")
    st.markdown(f"> {question}")

    with st.form("ask_human_form"):
        answer = st.text_area(
            "Your answer",
            placeholder="e.g. This is not a formed yoga — Jupiter is too weak. Proceed without it.",
            height=120,
            key=f"ask_human_answer_{abs(hash(question)) % 1_000_000}",
        )
        submitted = st.form_submit_button("Submit Answer →", type="primary", use_container_width=True)

    if submitted:
        if not answer.strip():
            st.error("Please provide an answer.")
        else:
            _ph = st.empty()
            with _ph:
                with st.spinner("Continuing synthesis…"):
                    resume_graph(answer.strip())
            _ph.empty()
            st.rerun()

# ── Screen 4: Checkpoint 2 — Draft Review ────────────────────────────────────

def show_checkpoint_2():
    idata = st.session_state.interrupt_data or {}
    draft = idata.get("draft_brief", "")
    revision = idata.get("revision_count", 0)

    st.title("Draft Review")
    if revision > 0:
        st.caption(f"Revision {revision}")
    st.caption("Review the AI-generated consultation brief. Approve it or request changes.")

    st.info("This is an AI-generated starting point. Edit directly in the box below, or request a revision.")

    edited_draft = st.text_area(
        "Consultation brief",
        value=draft,
        height=500,
        key="draft_editor",
    )

    st.divider()
    col_approve, col_revise = st.columns(2)

    with col_approve:
        if st.button("Approve Final Brief ✓", type="primary", use_container_width=True):
            _ph = st.empty()
            with _ph:
                with st.spinner("Finalising…"):
                    st.session_state.final_brief = edited_draft
                    resume_graph({"approved": True})
            _ph.empty()
            st.session_state.final_brief = edited_draft
            st.session_state.stage = "done"
            st.rerun()

    with col_revise:
        with st.expander("Request AI revision"):
            with st.form("revise_form"):
                feedback = st.text_area(
                    "What should change?",
                    placeholder="e.g. Add more detail on the 10th house. Remove the health section — not relevant today.",
                    height=100,
                )
                revise_btn = st.form_submit_button("Revise →", use_container_width=True)

            if revise_btn:
                if not feedback.strip():
                    st.error("Please describe what you'd like changed.")
                else:
                    _ph = st.empty()
                with _ph:
                    with st.spinner("Revising…"):
                        resume_graph({"approved": False, "feedback": feedback.strip()})
                _ph.empty()
                st.rerun()

# ── Screen 5: Final Brief ─────────────────────────────────────────────────────

def show_done():
    st.title("Final Consultation Brief")
    st.success("Brief approved. Ready for your consultation.")

    brief = st.session_state.final_brief or ""
    st.text_area("Brief", value=brief, height=600, key="final_brief_view", disabled=False, label_visibility="collapsed")

    col1, col2 = st.columns(2)
    col1.download_button(
        label="Download as .txt",
        data=brief,
        file_name="consultation_brief.txt",
        mime="text/plain",
        use_container_width=True,
    )
    if col2.button("Copy to clipboard (select all)", use_container_width=True):
        st.info("Click inside the text area above and press Cmd+A / Ctrl+A to select all, then copy.")

# ── Error screen ──────────────────────────────────────────────────────────────

def show_error():
    st.error("Something went wrong.")
    st.code(st.session_state.error or "Unknown error")
    if st.button("Start over"):
        for k in ["stage", "thread_id", "interrupt_data", "final_brief", "error"]:
            st.session_state[k] = None if k != "stage" else "intake"
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────

_sidebar()

stage = st.session_state.stage

if stage == "intake":
    show_intake()
elif stage == "checkpoint_1":
    show_checkpoint_1()
elif stage == "ask_human":
    show_ask_human()
elif stage == "checkpoint_2":
    show_checkpoint_2()
elif stage == "done":
    show_done()
elif stage == "error":
    show_error()
