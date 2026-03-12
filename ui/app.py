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
        for k in ["stage", "thread_id", "interrupt_data", "final_brief", "error"]:
            st.session_state[k] = None if k != "stage" else "intake"
        st.rerun()


def _planet_table(planets: dict) -> None:
    rows = []
    for planet, pos in planets.items():
        retro = "↺" if pos.get("retrograde") else ""
        rows.append({
            "Planet": planet,
            "Sign": pos.get("sign", ""),
            "House": pos.get("house", ""),
            "Nakshatra": pos.get("nakshatra", ""),
            "Pada": pos.get("nakshatra_pada", ""),
            "R": retro,
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

COMMON_TIMEZONES = [
    "Asia/Kolkata", "Asia/Colombo", "Asia/Kathmandu", "Asia/Dhaka",
    "Asia/Singapore", "Asia/Dubai", "Europe/London", "Europe/Paris",
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "Australia/Sydney", "Pacific/Auckland",
]

TOPICS = ["career", "marriage", "health", "education", "finance", "general"]


def show_intake():
    st.title("New Consultation")
    st.caption("Enter client birth details and the primary topic for today's session.")

    with st.form("intake_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Client")
            name = st.text_input("Client name", placeholder="e.g. Priya S.")
            topic = st.selectbox("Consultation topic", TOPICS, index=5)

        with col2:
            st.subheader("Birth details")
            birth_date = st.date_input(
                "Date of birth",
                value=None,
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )
            birth_time_str = st.text_input("Time of birth (HH:MM, 24h)", placeholder="14:32")
            birth_place = st.text_input("Place of birth", placeholder="Bangalore")

        st.subheader("Location (for chart calculation)")
        col3, col4, col5 = st.columns(3)
        with col3:
            latitude = st.number_input("Latitude", value=12.9716, format="%.4f", step=0.0001)
        with col4:
            longitude = st.number_input("Longitude", value=77.5946, format="%.4f", step=0.0001)
        with col5:
            timezone = st.selectbox("Timezone", COMMON_TIMEZONES)

        submitted = st.form_submit_button("Compute Chart →", use_container_width=True, type="primary")

    if submitted:
        # Validate
        errors = []
        if not name.strip():
            errors.append("Client name is required.")
        if birth_date is None:
            errors.append("Date of birth is required.")
        try:
            h, m = birth_time_str.strip().split(":")
            int(h), int(m)
        except Exception:
            errors.append("Birth time must be in HH:MM format (e.g. 14:32).")
        if not birth_place.strip():
            errors.append("Place of birth is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            initial_state = {
                "client_name": name.strip(),
                "birth_date": birth_date.isoformat(),
                "birth_time": birth_time_str.strip(),
                "birth_place": birth_place.strip(),
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "client_topic": topic,
                "human_answers": [],
                "revision_count": 0,
            }
            with st.spinner("Computing chart, dasha, and yogas…"):
                start_graph(initial_state)
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
        _planet_table(chart.get("planets", {}))

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
        with st.spinner("Synthesizing consultation brief… (agent may ask you a question)"):
            resume_graph({"approved": True, "corrections": corrections})
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
        )
        submitted = st.form_submit_button("Submit Answer →", type="primary", use_container_width=True)

    if submitted:
        if not answer.strip():
            st.error("Please provide an answer.")
        else:
            with st.spinner("Continuing synthesis…"):
                resume_graph(answer.strip())
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
            with st.spinner("Finalising…"):
                # Save the (possibly edited) draft, then approve
                st.session_state.final_brief = edited_draft
                resume_graph({"approved": True})
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
                    with st.spinner("Revising…"):
                        resume_graph({"approved": False, "feedback": feedback.strip()})
                    st.rerun()

# ── Screen 5: Final Brief ─────────────────────────────────────────────────────

def show_done():
    st.title("Final Consultation Brief")
    st.success("Brief approved. Ready for your consultation.")

    brief = st.session_state.final_brief or ""
    st.text_area("", value=brief, height=600, key="final_brief_view", disabled=False)

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
