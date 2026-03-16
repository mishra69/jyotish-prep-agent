"""
AgentState — the single source of truth flowing through the LangGraph graph.
All fields are plain JSON-serializable types so SQLite checkpointing works out of the box.
"""
from __future__ import annotations
from typing import Annotated, Any
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # ── Input (set at intake) ─────────────────────────────────────────────────
    client_name: str
    birth_date: str          # ISO date string "YYYY-MM-DD"
    birth_time: str          # "HH:MM"
    birth_place: str
    latitude: float
    longitude: float
    timezone: str            # IANA, e.g. "Asia/Kolkata"
    client_topics: list[str]  # e.g. ["career", "marriage"] — drives TOPIC_FOCUS guidance
    custom_topic: str         # free-text refinement or "other" topic description
    client_questions: str     # long-form questions the client brought to the session

    # ── Computed (from astro tools) ───────────────────────────────────────────
    birth_chart: dict[str, Any]    # serialized BirthChart
    dasha_data: dict[str, Any]     # serialized DashaData
    yogas: list[dict[str, Any]]    # serialized YogaResult list

    # ── Checkpoint 1: Prep review ─────────────────────────────────────────────
    checkpoint_1_approved: bool
    checkpoint_1_corrections: str  # free-text corrections/notes from astrologer

    # ── Synthesis: LLM conversation ───────────────────────────────────────────
    messages: Annotated[list, add_messages]   # accumulates across synthesis + revision

    # ── ask_human interactions ────────────────────────────────────────────────
    human_answers: list[dict[str, str]]  # [{"question": ..., "answer": ...}]

    # ── Checkpoint 2: Draft review ────────────────────────────────────────────
    draft_brief: str
    checkpoint_2_approved: bool
    checkpoint_2_feedback: str     # free-text feedback from astrologer

    # ── Control ───────────────────────────────────────────────────────────────
    revision_count: int            # number of revisions so far
    llm_model: str                 # OpenRouter model ID chosen at intake
