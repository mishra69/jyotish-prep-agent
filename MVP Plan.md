# Jyotish Prep Agent — MVP Plan

## Goal

Build an agentic AI system that automates Jyotish (Vedic astrology) consultation preparation with human-in-the-loop patterns. The primary audience is a job application demo showcasing agentic AI design. The secondary audience is a practicing Jyotish astrologer who will use it for real client consultations.

## Demo Story

"An agentic AI system with human-in-the-loop that helps a Jyotish astrologer prepare for consultations. The agent orchestrates computational tools, knows when to defer to the human expert, and collaboratively drafts a consultation brief."

## Architecture Overview

```
User Input (birth details + client question/topic)
        │
        ▼
   Orchestrator Agent (LangGraph)
        │
        ├──→ Tool: Kundli Calculator (birth chart)
        ├──→ Tool: Dasha Calculator (planetary periods)
        ├──→ Tool: Yoga Scanner (pattern identification)
        │
        ▼
   ┌─────────────────────────────────┐
   │  CHECKPOINT 1: Prep Review      │  ← Astrologer reviews computed data
   │  Approve / Correct / Recalculate│     Can fix birth time, flag issues
   └─────────────────────────────────┘
        │
        ▼
   Synthesis Agent (Claude API)
        │
        ├──→ May call ask_human tool ──→ Astrologer answers ──→ Agent continues
        │    (when agent encounters ambiguous patterns)
        │
        ▼
   ┌─────────────────────────────────┐
   │  CHECKPOINT 2: Draft Review      │  ← Astrologer edits/approves brief
   │  Approve / Edit / Regenerate     │
   └─────────────────────────────────┘
        │
        ▼
   Final Consultation Brief
```

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Agent framework | LangGraph (Python) | First-class HITL support via `interrupt_before`/`interrupt_after`, stateful graph with persistence |
| LLM | Claude (Anthropic API) | Strong reasoning for synthesis, good at structured output |
| Astro computation | flatlib or kerykeion (Swiss Ephemeris Python bindings) | Accurate sidereal/Lahiri ayanamsa calculations |
| Frontend | Streamlit | Fast to build, sufficient for single-user workflow, runs in browser |
| State persistence | SQLite | Lightweight, no external DB needed, checkpointed agent state |
| Deployment | GCP e2-micro (free tier) | Always-on, browser-accessible, zero cost |

## MVP Components

### Component 1: Astro Computation Engine (3 tools)

**Tool 1 — Kundli (Birth Chart) Generator**
- Input: date, time, place of birth
- Output: Lagna (ascendant), planetary positions (Sun through Ketu), house placements, sign placements, nakshatras
- Uses sidereal zodiac with Lahiri ayanamsa
- This is the foundation — everything else depends on it

**Tool 2 — Dasha Calculator**
- Input: birth chart data (from Tool 1)
- Output: Vimshottari dasha tree — Mahadasha → Antardasha → Pratyantardasha with start/end dates
- Highlights current period and next upcoming transition
- Clients almost always ask "what period am I in" — this is essential

**Tool 3 — Yoga Scanner**
- Input: birth chart data (from Tool 1)
- Output: list of yogas (planetary combinations) present in the chart with formation details
- Start with 15-20 major yogas (Raja Yoga, Gajakesari, Budhaditya, Viparita Raja Yoga, Neechabhanga Raja Yoga, etc.)
- This is where ambiguity lives — borderline formations trigger the `ask_human` tool
- Each yoga has clearly defined formation rules that can be checked programmatically

### Component 2: LangGraph Agent (Full-featured — this is the demo centerpiece)

**Graph structure:**
- Parallel tool execution for the 3 computation tools
- Checkpoint 1 (approval gate): pause after computation, wait for human review
- Synthesis node: LLM generates draft brief
- `ask_human` tool: available during synthesis, agent decides when to invoke
- Checkpoint 2 (approval gate): pause after draft, wait for human approval
- Iterative refinement loop: if human gives feedback at Checkpoint 2, agent revises

**`ask_human` tool — trigger rules (baked into system prompt):**
- A yoga's formation conditions are partially met (borderline case)
- Two classical rules give contradictory readings for the same house/topic
- Client's question touches a sensitive topic (health, death, legal) where astrologer should confirm emphasis
- A planet is within 1° of a house cusp (borderline placement)

**State schema:**
```python
class AgentState(TypedDict):
    # Input
    client_name: str
    birth_datetime: datetime
    birth_place: str
    client_topic: str  # e.g., "career", "marriage", "health"

    # Computed (Component 1 output)
    birth_chart: dict
    dasha_data: dict
    yogas: list[dict]

    # Human interactions
    human_corrections: list[str]  # from Checkpoint 1
    human_answers: list[dict]     # from ask_human calls

    # Synthesis
    draft_brief: str
    human_feedback: str           # from Checkpoint 2

    # Control
    approved: bool
```

### Component 3: Synthesis / Brief Generator

Prompt template that:
- Takes structured astro data + client topic
- Prioritizes relevant houses/planets based on topic (career → 10th house, marriage → 7th house, etc.)
- Flags notable patterns without asserting interpretation
- Generates a structured brief: Key Chart Features, Current Dasha Period, Relevant Yogas, Suggested Talking Points
- Draft analysis is clearly labeled as "AI-generated starting point"

### Component 4: Web UI (Streamlit)

**Screens:**
1. **Client intake form** — name, date, time, place, topic dropdown or free text
2. **Prep review (Checkpoint 1)** — displays computed chart data, approve / correct buttons
3. **Agent question (ask_human)** — shows agent's question with context, text input for response
4. **Draft review (Checkpoint 2)** — displays draft brief, editable text area, approve / regenerate buttons
5. **Final brief** — clean, printable view for use during consultation

### Component 5: Infrastructure

- GCP e2-micro VM (us-central1, free tier, permanently free)
- Python 3.11+ environment
- SQLite for state persistence
- Systemd service for process management
- HTTPS via Cloudflare or Caddy + Let's Encrypt
- Basic auth (username/password) to keep it private

## HITL Patterns Demonstrated (Demo Talking Points)

| Pattern | Where | What It Shows |
|---------|-------|---------------|
| Approval Gate | Checkpoint 1 and 2 | Agent pauses, human reviews, agent resumes. State persists across sessions. |
| Human-as-a-Tool | `ask_human` during synthesis | Agent recognizes its own uncertainty and invokes the human expert — same interface as any other tool call. |
| Iterative Refinement | Checkpoint 2 feedback loop | Human gives natural language feedback, agent revises. Multiple rounds supported. |
| Conditional Tool Use | Orchestrator choosing emphasis | Agent reasons about which computations are most relevant based on client topic. |

## What's OUT of MVP (V2 Backlog)

- Divisional charts (Navamsha D9, Dashamsha D10, etc.)
- Ashtakavarga scoring
- Transit analysis (current planetary positions vs birth chart)
- Client history / database of past consultations
- PDF export of final brief
- Multiple user accounts
- Mobile-optimized UI
- Expanded yoga library (beyond initial 15-20)
- Geocoding API integration (MVP can use manual lat/lon or a simple city lookup)

## Testing Strategy

### Computation tools (Component 1)
- Unit tests against known charts (verify against established Jyotish software)
- Edge cases: births near midnight, near date line, daylight saving transitions

### Agent behavior (Component 2)
- Synthetic test charts designed to trigger specific paths:
  - Clean chart (no ambiguity) → agent should NOT call `ask_human`
  - Chart with borderline Neechabhanga Raja Yoga → agent SHOULD call `ask_human`
  - Chart with contradictory indicators → agent SHOULD call `ask_human`
- LLM-as-judge evaluation: second LLM scores whether `ask_human` invocations were reasonable
- Record and replay: log all `ask_human` calls during real use for regression testing

### End-to-end
- 3-5 full workflow runs with different chart types and topics
- Verify state persistence: start workflow, close browser, reopen, resume from checkpoint

## File Structure

```
jyotish-prep-agent/
├── README.md
├── MVP_PLAN.md                  # This file
├── FULL_PLAN.md                 # Full feature roadmap
├── requirements.txt
├── .env.example                 # ANTHROPIC_API_KEY, etc.
│
├── astro/                       # Component 1: Computation engine
│   ├── __init__.py
│   ├── chart.py                 # Kundli/birth chart generation
│   ├── dasha.py                 # Vimshottari dasha calculation
│   ├── yogas.py                 # Yoga scanning rules
│   └── models.py                # Data classes for chart/planet/house
│
├── agent/                       # Component 2: LangGraph orchestrator
│   ├── __init__.py
│   ├── graph.py                 # LangGraph graph definition
│   ├── tools.py                 # Tool wrappers for astro functions
│   ├── human_tool.py            # ask_human tool implementation
│   ├── state.py                 # AgentState schema
│   └── prompts.py               # System prompts and templates
│
├── synthesis/                   # Component 3: Brief generation
│   ├── __init__.py
│   ├── brief.py                 # Brief generation logic
│   └── templates.py             # Topic-aware prompt templates
│
├── ui/                          # Component 4: Streamlit app
│   ├── app.py                   # Main Streamlit entry point
│   └── pages/
│       ├── 1_intake.py
│       ├── 2_prep_review.py
│       ├── 3_draft_review.py
│       └── 4_final_brief.py
│
├── tests/
│   ├── test_chart.py
│   ├── test_dasha.py
│   ├── test_yogas.py
│   ├── test_agent.py
│   └── fixtures/
│       └── charts.json          # Known test charts with verified data
│
└── deploy/
    ├── setup_gcp.sh             # VM provisioning script
    ├── jyotish.service          # Systemd unit file
    └── Caddyfile                # HTTPS reverse proxy config
```

## Development Sequence

1. **Week 1**: Component 1 — birth chart and dasha calculator, verify against known software
2. **Week 2**: Component 1 (yoga scanner) + Component 2 — yoga rules, LangGraph graph with all HITL patterns
3. **Week 3**: Component 3 + Component 4 — synthesis prompts, Streamlit UI
4. **Week 4**: Component 5 + testing + polish — deploy to GCP, end-to-end tests, demo rehearsal

## Open Questions (To Resolve With Sister)

- [ ] Which yogas does she most commonly look for? (Prioritize in initial 15-20)
- [ ] What does her current prep workflow look like? (Software, manual steps, time spent)
- [ ] What format does she want the final brief in? (Sections, detail level, language)
- [ ] Does she use North Indian or South Indian chart style? (Affects UI display)
- [ ] What topics do clients most commonly ask about? (Prioritize topic-aware templates)
- [ ] Any sensitive topics where she'd always want the tool to defer to her? (Configure ask_human triggers)
