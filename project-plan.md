# Jyotish Prep Agent — Project Plan

## Overview

An agentic AI tool that automates Vedic astrology (Jyotish) consultation preparation. The system computes birth charts, identifies planetary periods and yogas, then uses an LLM to synthesize a structured consultation brief — with the astrologer staying in the loop at every critical decision point.

**Primary goal**: Demonstrate agentic AI patterns (tool use, human-in-the-loop, iterative refinement) for a portfolio/job application.

**Secondary goal**: Build a genuinely useful tool for a practicing Jyotish consultant.

---

## Architecture

```
User Input (birth details + question topic)
        │
        ▼
   Orchestrator Agent (LangGraph)
        │
        ├──→ Tool: Kundli Calculator (Swiss Ephemeris)
        ├──→ Tool: Dasha Calculator
        ├──→ Tool: Transit Fetcher
        ├──→ Tool: Yoga Scanner
        ├──→ Tool: Ashtakavarga Calculator
        │
        ▼
   ┌─────────────────────────────┐
   │  CHECKPOINT 1: Prep Review  │  ← Astrologer reviews computed data
   └─────────────────────────────┘
        │
        ▼
   Synthesis Agent (LLM)
        │
        ├──→ (may call ask_human tool if uncertain)
        │
        ▼
   ┌─────────────────────────────┐
   │  CHECKPOINT 2: Draft Review │  ← Astrologer edits/approves brief
   └─────────────────────────────┘
        │
        ▼
   Final Consultation Brief
```

### HITL Patterns Demonstrated

1. **Approval Gates** — Agent pauses at Checkpoints 1 and 2, waits for human approval before proceeding.
2. **Human-as-a-Tool** — During synthesis, the agent can call `ask_human` when it encounters ambiguous astrological configurations. The LLM decides when to invoke this.
3. **Iterative Refinement** — After the draft brief, the astrologer can give natural language feedback and the agent revises.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Agent Framework | LangGraph (Python) | Multi-step tool-using agent with HITL support via `interrupt_before` |
| LLM | Claude (Anthropic API) | Synthesis and agent reasoning |
| Astro Computation | flatlib or kerykeion (Swiss Ephemeris) | Sidereal zodiac, Lahiri ayanamsa |
| Frontend | Streamlit | Browser-based, touch-acceptable |
| State Storage | SQLite | Agent checkpoints and client history |
| Deployment (MVP) | Local (Mac for dev) | Sister accesses via browser |
| Deployment (Full) | GCP e2-micro free tier | Always-on, HTTPS via Cloudflare |

---

## Components

### Component 1: Astro Computation Engine

Pure Python calculation layer. No LLM involved.

| Deliverable | Description | MVP | Full |
|---|---|---|---|
| Birth chart (Kundli) | Planetary positions, house placements, ascendant (sidereal/Lahiri) | ✅ | ✅ |
| Dasha calculator | Vimshottari dasha tree with date ranges, current period highlighted | ✅ | ✅ |
| Yoga scanner | Checks chart against yoga definitions, returns matches | ✅ | ✅ |
| Divisional charts | Navamsha (D9), Dashamsha (D10), others | ❌ | ✅ |
| Ashtakavarga | Scores per planet per house, sarvashtakavarga totals | ❌ | ✅ |
| Transit calculator | Current planetary positions relative to birth chart | ❌ | ✅ |

**Input**: Date, time, place of birth
**Output**: Structured JSON with all computed data

### Component 2: LangGraph Agent (Orchestrator)

The agentic layer. This is the star of the demo.

| Deliverable | Description | MVP | Full |
|---|---|---|---|
| Agent graph definition | Full graph with all three HITL patterns | ✅ | ✅ |
| Tool wrappers | Each Component 1 calculation as a LangGraph tool | ✅ | ✅ |
| `ask_human` tool | With confidence trigger rules in system prompt | ✅ | ✅ |
| State schema | Birth data, computed results, human corrections, draft, approval | ✅ | ✅ |
| System prompt | Topic-aware orchestration, escalation rules, synthesis instructions | ✅ | ✅ |

### Component 3: Synthesis / Brief Generator

LLM-powered layer that turns raw data into a readable brief.

| Deliverable | Description | MVP | Full |
|---|---|---|---|
| Prompt template | Structured astro data + topic → organized brief | ✅ | ✅ |
| Topic-aware prioritization | Emphasize relevant houses/planets based on client question | ✅ (career + general) | ✅ (career, marriage, health, education, finance, general) |
| Pattern flagging | Surface notable configurations without asserting interpretation | ✅ | ✅ |
| Optional draft analysis | Starting point astrologer can edit or discard | ✅ | ✅ |

### Component 4: Web UI

What the astrologer sees and interacts with.

| Deliverable | Description | MVP | Full |
|---|---|---|---|
| Client intake form | Name, date/time/place of birth, topic | ✅ | ✅ |
| Checkpoint 1 screen | Display computed data, allow corrections | ✅ | ✅ |
| `ask_human` screen | Show agent's question, accept text response | ✅ | ✅ |
| Checkpoint 2 screen | Display draft brief, inline edit, approve/regenerate | ✅ | ✅ |
| Final brief view | Clean, printable version | ✅ | ✅ |
| Client list/history | Past consultations, revisitable | ❌ | ✅ |
| Client management | Add/edit/delete clients | ❌ | ✅ |

### Component 5: Infrastructure & Deployment

| Deliverable | Description | MVP | Full |
|---|---|---|---|
| Local dev setup | Python env, dependencies, run locally | ✅ | ✅ |
| GCP VM setup | e2-micro, persistent disk, firewall rules | ❌ | ✅ |
| Systemd service | App stays running after SSH disconnect | ❌ | ✅ |
| HTTPS | Cloudflare or Caddy + Let's Encrypt | ❌ | ✅ |
| Auth | Basic login so it's not open to the internet | ❌ | ✅ |
| Deploy script | Push updates from Mac | ❌ | ✅ |

---

## Dependency Order

```
Component 1 (Astro Engine)     — no dependencies, start here
     │
     ▼
Component 3 (Synthesis)        — needs Component 1's output format
     │
     ▼
Component 2 (Agent/LangGraph)  — wires together 1 and 3, adds HITL
     │
     ▼
Component 4 (UI)               — needs Component 2's state/flow
     │
     ▼
Component 5 (Infra)            — needs everything working locally first
```

---

## Testing Strategy

### Astro Engine (Component 1)
- Unit tests against known chart data (e.g., well-documented celebrity charts)
- Validate against output from established Jyotish software

### Human-as-a-Tool Path (Component 2)
- Define explicit trigger rules in the system prompt (borderline yoga formation, contradictory readings, sensitive topics, borderline house cusps)
- Build synthetic test charts designed to hit those triggers
- Build clean test charts that should NOT trigger escalation
- Use LLM-as-judge to evaluate whether the agent's questions were reasonable
- Log all `ask_human` invocations in production for regression testing

### Synthesis (Component 3)
- Evaluate briefs against rubric: correct prioritization for topic, no hallucinated yogas, flagging without over-interpreting
- Sister reviews sample briefs and scores them

### End-to-End
- 3-4 complete test scenarios covering: clean chart (no human escalation), ambiguous chart (human-as-tool fires), user correction at checkpoint 1, iterative refinement at checkpoint 2

---

## Sample Consultation Brief Output

```
═══ CONSULTATION BRIEF ═══
Client: Priya S.  |  Topic: Career Growth
Born: 15-Mar-1990, 14:32 IST, Bangalore

LAGNA: Karkataka (Cancer) | Moon in Rohini (Taurus)

CURRENT DASHA: Jupiter Mahadasha → Saturn Antardasha
  → Jupiter is 9th lord (fortune) in 10th (career): strong placement
  → Saturn is 7th & 8th lord: watch for partnership tensions at work
  → Period runs until: Aug 2026

KEY YOGAS IDENTIFIED:
  ✦ Gajakesari Yoga (Jupiter-Moon) — reputation & wisdom
  ✦ Budhaditya Yoga (Sun-Mercury in 9th) — analytical talent

10TH HOUSE ANALYSIS:
  Lord: Mars in 3rd house (Virgo) — self-made effort, communication-driven career

FLAGGED FOR REVIEW:
  ⚠ Possible Neechabhanga Raja Yoga — Saturn debilitated in 10th but
    cancellation conditions partially met. Agent asked astrologer for
    confirmation. [Astrologer response: "Not formed, Jupiter too weak"]

SUGGESTED TALKING POINTS:
  1. Career growth supported but Saturn antardasha adds friction
  2. Dasha transition upcoming — discuss timeline
  3. [Astrologer's added note: Focus on 3rd house Mars — client
     is in communications industry]
═══
```
