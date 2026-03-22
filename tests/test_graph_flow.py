"""
Integration tests for the LangGraph agent flow.

Mocks ChatOpenAI so no real API calls are made.
Tests the complete flow: compute → checkpoint_1 → synthesis (with ask_human)
→ checkpoint_2 → revision → checkpoint_2 → approve.

Key invariants verified:
- ask_human interrupts are properly routed and executed
- human_answers is reset on revision (fresh ask_human budget)
- revision request appears exactly once in messages sent to LLM
- draft_brief is the actual brief, not a tool-call preamble
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import AIMessage
from langgraph.types import Command

# ── Helpers ───────────────────────────────────────────────────────────────────

# A fixed, real-ish birth input — astro computation runs but makes no network calls
TEST_INPUT = {
    "client_name": "Test Client",
    "birth_date": "1990-06-15",
    "birth_time": "08:30",
    "birth_place": "Mumbai, India",
    "latitude": 19.076,
    "longitude": 72.878,
    "timezone": "Asia/Kolkata",
    "client_topics": ["general"],
    "custom_topic": "",
    "client_questions": "",
    "llm_model": "test-model",
}

DRAFT_1 = (
    "CONSULTATION BRIEF\n"
    "Client: Test Client  |  Topic: general\n"
    "Born: 1990-06-15 08:30, Mumbai, India\n\n"
    "LAGNA: Gemini\n\n"
    "CURRENT DASHA: Mercury Mahadasha / Saturn Antardasha\n"
    "  - Period runs until: 2026-01-01\n\n"
    "KEY YOGAS:\n  - Budhaditya Yoga -- Sun and Mercury conjunct.\n\n"
    "GENERAL HOUSE ANALYSIS:\n  - Lagna lord Mercury in 10th.\n\n"
    "FLAGGED ITEMS:\n  - None.\n\n"
    "SUGGESTED TALKING POINTS:\n  1. Career focus during Mercury dasha."
)

DRAFT_2 = (
    "CONSULTATION BRIEF\n"
    "Client: Test Client  |  Topic: marriage\n"
    "Born: 1990-06-15 08:30, Mumbai, India\n\n"
    "LAGNA: Gemini\n\n"
    "CURRENT DASHA: Mercury Mahadasha / Saturn Antardasha\n"
    "  - Period runs until: 2026-01-01\n\n"
    "KEY YOGAS:\n  - Raja Yoga -- 7th lord conjunct lagna lord.\n\n"
    "MARRIAGE HOUSE ANALYSIS:\n  - 7th house lord Venus in 11th.\n\n"
    "FLAGGED ITEMS:\n  - None.\n\n"
    "SUGGESTED TALKING POINTS:\n  1. Venus period favourable for marriage."
)


def _ai_draft(text):
    """AIMessage with plain text content — no tool calls."""
    return AIMessage(content=text)


def _ai_ask(question, call_id="tc1"):
    """AIMessage with a single ask_human tool call."""
    msg = AIMessage(content="")
    msg.tool_calls = [
        {"name": "ask_human", "args": {"question": question},
         "id": call_id, "type": "tool_call"}
    ]
    return msg


class _CannedLLM:
    """Returns a predetermined sequence of AIMessages."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._index = 0
        self.calls = []  # captures (call_index, messages) for inspection

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        idx = self._index
        self.calls.append((idx, list(messages)))
        if idx >= len(self._responses):
            raise AssertionError(
                f"LLM called {idx + 1} times but only {len(self._responses)} "
                "responses were configured"
            )
        self._index += 1
        return self._responses[idx]


def _interrupts(state):
    """Extract all interrupt values from a graph state."""
    return [
        i.value
        for task in (state.tasks or [])
        for i in (getattr(task, "interrupts", None) or [])
    ]


# ── Test cases ────────────────────────────────────────────────────────────────

class TestGraphFlow(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except FileNotFoundError:
            pass

    def _build(self, llm):
        from agent.graph import build_graph
        return build_graph(self._db_path)

    def _advance_through_checkpoint_1(self, graph, config, llm_patcher):
        """Run graph to checkpoint_1 and auto-approve it."""
        graph.invoke(TEST_INPUT, config)
        state = graph.get_state(config)
        intrs = _interrupts(state)
        self.assertTrue(
            any(isinstance(v, dict) and v.get("type") == "checkpoint_1" for v in intrs),
            f"Expected checkpoint_1 interrupt, got: {intrs}"
        )
        graph.invoke(Command(resume={"approved": True, "corrections": ""}), config)

    # ── 1. Happy path: no ask_human ──────────────────────────────────────────

    def test_direct_synthesis_reaches_checkpoint_2_with_correct_draft(self):
        """LLM returns a draft immediately → checkpoint_2 has the correct draft_brief."""
        llm = _CannedLLM([_ai_draft(DRAFT_1)])

        with patch("agent.graph.ChatOpenAI", return_value=llm):
            graph = self._build(llm)
            config = {"configurable": {"thread_id": "t-direct"}}
            self._advance_through_checkpoint_1(graph, config, None)

            state = graph.get_state(config)
            intrs = _interrupts(state)
            cp2 = next((v for v in intrs if isinstance(v, dict) and v.get("type") == "checkpoint_2"), None)
            self.assertIsNotNone(cp2, "Expected checkpoint_2 interrupt")
            # draft_brief is in the interrupt payload (node is paused before returning)
            self.assertEqual(cp2["draft_brief"], DRAFT_1)

    # ── 2. ask_human is executed and answered ────────────────────────────────

    def test_ask_human_fires_and_graph_resumes_to_checkpoint_2(self):
        """LLM calls ask_human → graph pauses with ask_human interrupt → answer → checkpoint_2."""
        llm = _CannedLLM([_ai_ask("Should I include Adhi Yoga?", "tc1"), _ai_draft(DRAFT_1)])

        with patch("agent.graph.ChatOpenAI", return_value=llm):
            graph = self._build(llm)
            config = {"configurable": {"thread_id": "t-ask"}}
            self._advance_through_checkpoint_1(graph, config, None)

            # Should pause at ask_human
            state = graph.get_state(config)
            intrs = _interrupts(state)
            ask_intr = next((v for v in intrs if isinstance(v, dict) and v.get("type") == "ask_human"), None)
            self.assertIsNotNone(ask_intr, f"Expected ask_human interrupt, got: {intrs}")
            self.assertIn("Adhi Yoga", ask_intr["question"])

            # Answer → should advance to checkpoint_2
            graph.invoke(Command(resume="exclude"), config)
            state = graph.get_state(config)
            intrs = _interrupts(state)
            cp2 = next((v for v in intrs if isinstance(v, dict) and v.get("type") == "checkpoint_2"), None)
            self.assertIsNotNone(cp2, "Expected checkpoint_2 after answering ask_human")
            # draft is in interrupt payload (node paused before returning)
            self.assertEqual(cp2["draft_brief"], DRAFT_1)
            self.assertEqual(len(state.values.get("human_answers", [])), 1)

    # ── 3. human_answers resets on revision ──────────────────────────────────

    def test_human_answers_reset_on_revision_allows_ask_human(self):
        """
        First synthesis uses 2 ask_human calls (hits MAX_ASK_HUMAN).
        After revision feedback, human_answers is reset to [] so ask_human
        fires again in the revision pass instead of being silently blocked.
        """
        llm = _CannedLLM([
            _ai_ask("Include Adhi Yoga?",      "tc1"),
            _ai_ask("Include Saraswati Yoga?", "tc2"),
            _ai_draft(DRAFT_1),
            # Revision pass — LLM asks one more question (should now be allowed)
            _ai_ask("Marriage focus: 7th lord or Venus?", "tc3"),
            _ai_draft(DRAFT_2),
        ])

        with patch("agent.graph.ChatOpenAI", return_value=llm):
            graph = self._build(llm)
            config = {"configurable": {"thread_id": "t-reset"}}
            self._advance_through_checkpoint_1(graph, config, None)

            graph.invoke(Command(resume="exclude"), config)   # answer ask_human #1
            graph.invoke(Command(resume="exclude"), config)   # answer ask_human #2

            state = graph.get_state(config)
            self.assertEqual(len(state.values.get("human_answers", [])), 2,
                             "Should have 2 human_answers after first synthesis")

            # Give revision feedback
            graph.invoke(Command(resume={"approved": False, "feedback": "make it about marriage"}), config)

            state = graph.get_state(config)
            self.assertEqual(state.values.get("human_answers"), [],
                             "human_answers should be reset to [] on revision")

            # The revision LLM call fired ask_human — graph should be paused there
            intrs = _interrupts(state)
            ask_intr = next((v for v in intrs if isinstance(v, dict) and v.get("type") == "ask_human"), None)
            self.assertIsNotNone(
                ask_intr,
                "Revision ask_human should execute, not be silently blocked by old human_answers count"
            )

            # Answer revision question → revised draft appears in new checkpoint_2 interrupt
            graph.invoke(Command(resume="yes, focus on 7th lord"), config)
            state = graph.get_state(config)
            intrs = _interrupts(state)
            cp2 = next((v for v in intrs if isinstance(v, dict) and v.get("type") == "checkpoint_2"), None)
            self.assertIsNotNone(cp2, "Expected checkpoint_2 after revision LLM call")
            self.assertEqual(cp2["draft_brief"], DRAFT_2)

    # ── 4. Revision request appears exactly once in LLM messages ─────────────

    def test_revision_request_not_duplicated_in_llm_messages(self):
        """
        The revision request should appear exactly once in the messages sent
        to the LLM — as a HumanMessage at the end of the conversation.
        It must NOT also appear inside the first HumanMessage from build_synthesis_message.
        """
        llm = _CannedLLM([_ai_draft(DRAFT_1), _ai_draft(DRAFT_2)])

        with patch("agent.graph.ChatOpenAI", return_value=llm):
            graph = self._build(llm)
            config = {"configurable": {"thread_id": "t-nodupe"}}
            self._advance_through_checkpoint_1(graph, config, None)
            # Approve checkpoint_2 with revision feedback
            graph.invoke(Command(resume={"approved": False, "feedback": "make it about marriage"}), config)

        # LLM was called twice: first for initial synthesis, second for revision
        self.assertEqual(len(llm.calls), 2, f"Expected 2 LLM calls, got {len(llm.calls)}")

        _, revision_messages = llm.calls[1]
        full_text = " ".join(
            str(getattr(m, "content", "")) for m in revision_messages
        )
        count = full_text.lower().count("make it about marriage")
        self.assertEqual(count, 1,
                         f"Revision request appeared {count} times in LLM messages, expected exactly 1")

    # ── 5. Full approved flow ends graph ─────────────────────────────────────

    def test_approval_ends_graph(self):
        """After checkpoint_2 approval, graph completes with no pending next steps."""
        llm = _CannedLLM([_ai_draft(DRAFT_1)])

        with patch("agent.graph.ChatOpenAI", return_value=llm):
            graph = self._build(llm)
            config = {"configurable": {"thread_id": "t-done"}}
            self._advance_through_checkpoint_1(graph, config, None)
            graph.invoke(Command(resume={"approved": True}), config)

            state = graph.get_state(config)
            self.assertFalse(state.next, "Graph should have no pending steps after approval")
            self.assertEqual(state.values.get("draft_brief"), DRAFT_1)


if __name__ == "__main__":
    unittest.main()
