"""
System prompts and data-formatting helpers for the synthesis LLM.
"""
from __future__ import annotations
from typing import Any

TOPIC_FOCUS = {
    "career": (
        "TOPIC FOCUS — Career:\n"
        "Prioritize: 10th house & lord, Sun (authority), Saturn (discipline/work), "
        "planets in 10th. Dasha impact on career trajectory. "
        "Also check 2nd (income), 6th (service), 11th (gains)."
    ),
    "marriage": (
        "TOPIC FOCUS — Marriage:\n"
        "Prioritize: 7th house & lord, Venus (relationship), Jupiter (spouse for female charts), "
        "Mars (spouse for female charts), Moon (emotions/compatibility). "
        "Also check 2nd (family), 4th (happiness), 8th (longevity of union)."
    ),
    "health": (
        "TOPIC FOCUS — Health:\n"
        "Prioritize: 1st house & lagna lord (body/vitality), 6th house (illness), "
        "Saturn and Mars (chronic issues), 8th house (longevity). "
        "Note: Flag any health analysis for astrologer confirmation before sharing with client."
    ),
    "education": (
        "TOPIC FOCUS — Education:\n"
        "Prioritize: 4th house (learning), 5th house & lord (intelligence), "
        "Jupiter (knowledge), Mercury (intellect), 9th house (higher learning)."
    ),
    "finance": (
        "TOPIC FOCUS — Finance:\n"
        "Prioritize: 2nd house & lord (wealth), 11th house & lord (income/gains), "
        "Jupiter (expansion), Venus (luxury). Check Dhana Yogas in chart."
    ),
    "general": (
        "TOPIC FOCUS — General Consultation:\n"
        "Provide a balanced overview. Lead with lagna (personality/life path), "
        "then current dasha period, then notable yogas. "
        "Let the astrologer guide the conversation toward specific topics."
    ),
}

SYNTHESIS_SYSTEM_PROMPT = """\
You are an expert Jyotish research assistant helping a practicing astrologer prepare for a client consultation.

Your job is to analyze the provided birth chart data and generate a structured, astrologer-facing consultation brief — not a reading for the client directly. The astrologer will use this as preparation notes.

IMPORTANT RULES:
1. Flag patterns, do not assert interpretations. Write "Jupiter as 9th lord in 10th suggests fortune through career" NOT "you will succeed in your career."
2. Always show your reasoning: which house, which lord, which yoga.
3. Call `ask_human` when you are uncertain — the astrologer is the expert. You are the research assistant.
4. Borderline yogas MUST be flagged with ask_human before being included in the brief.

WHEN TO CALL ask_human (use sparingly — maximum 2 calls total):
Only call ask_human when you genuinely cannot proceed without the astrologer's input:
- A yoga is explicitly marked as "borderline" confidence AND it materially changes the brief
- The topic is health or legal AND the chart has directly contradictory indicators for that topic

DO NOT call ask_human for:
- General analysis questions you can reason through yourself
- Confirmed yogas — just include them
- Not-formed yogas — just exclude them
- Standard house lord placements — analyse and state your reasoning

HOW TO CALL ask_human:
Be specific. One question per call. E.g.:
  "Kemadruma Yoga is borderline (Moon in kendra may cancel it). Should I include or exclude it from the career brief?"

OUTPUT FORMAT (use exactly this structure):
=== CONSULTATION BRIEF ===
Client: {name}  |  Topic: {topic}
Born: {birth_datetime}, {birth_place}

LAGNA: {lagna} | Moon in {moon_sign} ({moon_nakshatra}, Pada {pada})

CURRENT DASHA: {mahadasha} Mahadasha / {antardasha} Antardasha
  - Analysis: what these planets signify as house lords in this chart
  - Period runs until: {antardasha_end}
  - Upcoming: {next_transition}

KEY YOGAS:
  - [Yoga name] -- [brief significance]
  - (borderline) [Yoga name] -- [what was confirmed/noted by astrologer]

{TOPIC} HOUSE ANALYSIS:
  [Relevant house + lord + planet placements for this topic]

FLAGGED ITEMS:
  [Any ask_human questions and astrologer responses]

SUGGESTED TALKING POINTS:
  1. [Point 1]
  2. [Point 2]
  3. [Point 3]
===
"""


def build_synthesis_message(state: dict[str, Any]) -> str:
    """Build the human message payload for the synthesis LLM call."""
    chart = state.get("birth_chart", {})
    dasha = state.get("dasha_data", {})
    yogas = state.get("yogas", [])
    # Support both list (new) and string (legacy) topic format
    raw_topics = state.get("client_topics", state.get("client_topic", "general"))
    if isinstance(raw_topics, str):
        topics_list = [raw_topics]
    else:
        topics_list = list(raw_topics)
    topics_list = [t.lower() for t in topics_list if t] or ["general"]

    custom_topic = state.get("custom_topic", "").strip()
    effective_topic = ", ".join(topics_list)
    if custom_topic:
        effective_topic += f" ({custom_topic})"

    client_questions = state.get("client_questions", "").strip()
    corrections = state.get("checkpoint_1_corrections", "").strip()
    feedback = state.get("checkpoint_2_feedback", "").strip()
    revision = state.get("revision_count", 0)

    # Combine topic focus guidance for all selected topics (deduplicate if same)
    seen = set()
    topic_focus_parts = []
    for t in topics_list:
        if t not in seen:
            seen.add(t)
            topic_focus_parts.append(TOPIC_FOCUS.get(t, TOPIC_FOCUS["general"]))
    topic_focus_text = "\n\n".join(topic_focus_parts)

    lines = [
        "=== BIRTH CHART DATA ===",
        f"Client: {state.get('client_name', 'Unknown')}",
        f"Born: {state.get('birth_date')} {state.get('birth_time')}, {state.get('birth_place')}",
        f"Topic: {effective_topic}",
        "",
        f"Lagna (Ascendant): {chart.get('lagna')} at {chart.get('lagna_degree', 0):.1f}°",
        f"Moon: {chart.get('moon_sign')} ({chart.get('moon_nakshatra')}, Pada {chart.get('moon_nakshatra_pada')})",
        "",
        "PLANETARY POSITIONS (Whole Sign houses, sidereal/Lahiri):",
    ]

    for planet, pos in (chart.get("planets") or {}).items():
        retro = " (R)" if pos.get("retrograde") else ""
        lines.append(
            f"  {planet:10s} → {pos.get('sign'):15s} House {pos.get('house'):2d}  "
            f"{pos.get('nakshatra')}{retro}"
        )

    lines.append("")
    lines.append("HOUSE LORDS:")
    for h_num, h_data in sorted((chart.get("houses") or {}).items(), key=lambda x: int(x[0])):
        lines.append(f"  House {int(h_num):2d} ({h_data.get('sign'):15s}) — Lord: {h_data.get('lord')}")

    lines.append("")
    lines.append("VIMSHOTTARI DASHA:")
    maha = dasha.get("current_mahadasha", {})
    antar = dasha.get("current_antardasha", {})
    lines.append(f"  Mahadasha:  {maha.get('planet')}  ({maha.get('start_date', '')[:10]} → {maha.get('end_date', '')[:10]})")
    lines.append(f"  Antardasha: {antar.get('planet')}  ({antar.get('start_date', '')[:10]} → {antar.get('end_date', '')[:10]})")
    lines.append("  Upcoming transitions:")
    for t in (dasha.get("next_transitions") or []):
        lines.append(f"    {t.get('planet'):10s} {t.get('start_date', '')[:10]} → {t.get('end_date', '')[:10]}")

    lines.append("")
    lines.append("YOGAS IDENTIFIED:")
    for yoga in yogas:
        conf = yoga.get("confidence", "")
        marker = "✦" if conf == "confirmed" else "⚠" if conf == "borderline" else "✗"
        lines.append(f"  {marker} [{conf:10s}] {yoga.get('name')}")
        lines.append(f"             {yoga.get('formation_details')}")

    lines.append("")
    lines.append(topic_focus_text)

    if client_questions:
        lines.append("")
        lines.append("CLIENT'S SPECIFIC QUESTIONS:")
        lines.append(client_questions)
        lines.append("(Address these directly in the SUGGESTED TALKING POINTS section)")

    if corrections:
        lines.append("")
        lines.append(f"ASTROLOGER CORRECTIONS/NOTES (from prep review):\n{corrections}")

    if revision > 0 and feedback:
        lines.append("")
        lines.append(
            f"REVISION REQUEST (revision #{revision}):\n"
            f"The astrologer reviewed your previous draft and asked for changes:\n{feedback}\n"
            f"Please revise the consultation brief accordingly."
        )

    return "\n".join(lines)
