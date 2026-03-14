"""
End-to-end graph integration test.
Runs the full pipeline with a hardcoded chart, auto-responding to all interrupts.
No UI needed — just run: venv/bin/python tests/run_graph.py

Set GROQ_API_KEY in your .env before running.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import uuid
from langgraph.types import Command
from agent.graph import build_graph

# ── Test chart: Priya S. ──────────────────────────────────────────────────────

INITIAL_STATE = {
    "client_name": "Priya S.",
    "birth_date": "1990-03-15",
    "birth_time": "14:32",
    "birth_place": "Bangalore",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "timezone": "Asia/Kolkata",
    "client_topics": ["career"],
    "custom_topic": "",
    "client_questions": "",
    "human_answers": [],
    "revision_count": 0,
}


def run():
    graph = build_graph(":memory:")
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print("=" * 60)
    print("Jyotish Prep Agent — Integration Test")
    print("Chart: Priya S., 15-Mar-1990, 14:32 IST, Bangalore")
    print("Topic: Career")
    print("=" * 60)

    input_data = INITIAL_STATE
    step = 0

    while True:
        step += 1
        print(f"\n[Step {step}] Running graph...")
        interrupt_data = None

        for chunk in graph.stream(input_data, config=config, stream_mode="updates"):
            for node, updates in chunk.items():
                if node == "__interrupt__":
                    idata = updates[0].value if hasattr(updates[0], "value") else updates[0]
                    interrupt_data = idata
                    print(f"  → Interrupt: {idata.get('type')}")
                else:
                    print(f"  → Node completed: {node}")

        if interrupt_data is None:
            # Graph finished
            final_state = graph.get_state(config)
            brief = (final_state.values or {}).get("draft_brief", "")
            print("\n" + "=" * 60)
            print("FINAL BRIEF:")
            print("=" * 60)
            print(brief or "(empty)")
            break

        itype = interrupt_data.get("type")

        if itype == "checkpoint_1":
            chart = interrupt_data.get("birth_chart", {})
            print(f"  Lagna: {chart.get('lagna')}  Moon: {chart.get('moon_sign')} ({chart.get('moon_nakshatra')})")
            yogas = interrupt_data.get("yogas", [])
            relevant = [y for y in yogas if y.get("confidence") != "not_formed"]
            print(f"  Yogas: {len(relevant)} relevant ({sum(1 for y in relevant if y.get('confidence')=='confirmed')} confirmed, "
                  f"{sum(1 for y in relevant if y.get('confidence')=='borderline')} borderline)")
            dasha = interrupt_data.get("dasha_data", {})
            maha = dasha.get("current_mahadasha", {})
            antar = dasha.get("current_antardasha", {})
            print(f"  Dasha: {maha.get('planet')} Maha → {antar.get('planet')} Antar")
            print("  [AUTO] Approving checkpoint 1...")
            input_data = Command(resume={"approved": True, "corrections": ""})

        elif itype == "ask_human":
            question = interrupt_data.get("question", "")
            print(f"  Agent question: {question[:120]}...")
            answer = "Please use your best judgment and proceed with the analysis."
            print(f"  [AUTO] Answering: {answer}")
            input_data = Command(resume=answer)

        elif itype == "checkpoint_2":
            draft = interrupt_data.get("draft_brief", "")
            print(f"  Draft length: {len(draft)} chars")
            if draft:
                print("\n--- DRAFT PREVIEW (first 500 chars) ---")
                print(draft[:500])
                print("---")
            else:
                print("  WARNING: Draft is empty!")
            print("  [AUTO] Approving checkpoint 2...")
            input_data = Command(resume={"approved": True})

        else:
            print(f"  Unknown interrupt type: {itype}")
            break


if __name__ == "__main__":
    run()
