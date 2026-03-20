"""
LangGraph orchestrator for the Jyotish Prep Agent.

Graph flow:
  compute → checkpoint_1 → llm_call ←──────────────────┐
                                 │                      │
                      [has tool calls]           [needs revision]
                                 │                      │
                           run_tools             checkpoint_2
                                 │                      │
                           [back to]             [approved] → END
                            llm_call
                                 │
                       [no tool calls]
                                 │
                           checkpoint_2
"""
from __future__ import annotations

import logging
import os
from typing import Literal

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.state import AgentState
from agent.tools import tool_compute_chart, tool_compute_dasha, tool_compute_yogas, SYNTHESIS_TOOLS
from agent.prompts import SYNTHESIS_SYSTEM_PROMPT, build_synthesis_message

MAX_REVISIONS = 5
MAX_ASK_HUMAN = 2   # hard cap on ask_human calls per synthesis
MAX_LLM_ITERATIONS = 6  # hard cap on llm_call → run_tools cycles


# ── Node: compute ─────────────────────────────────────────────────────────────

def compute_node(state: AgentState) -> dict:
    """Run all three astro computations sequentially."""
    chart = tool_compute_chart.invoke({
        "client_name": state["client_name"],
        "birth_date": state["birth_date"],
        "birth_time": state["birth_time"],
        "birth_place": state["birth_place"],
        "latitude": state["latitude"],
        "longitude": state["longitude"],
        "timezone": state["timezone"],
    })
    dasha = tool_compute_dasha.invoke({"birth_chart": chart})
    yogas = tool_compute_yogas.invoke({"birth_chart": chart})

    return {
        "birth_chart": chart,
        "dasha_data": dasha,
        "yogas": yogas,
    }


# ── Node: checkpoint_1 ────────────────────────────────────────────────────────

def checkpoint_1_node(state: AgentState) -> dict:
    """
    HITL Pattern 1 — Approval Gate.
    Pause and present computed chart data to the astrologer.
    Wait for approval (and optional corrections) before synthesis.
    """
    response = interrupt({
        "type": "checkpoint_1",
        "birth_chart": state["birth_chart"],
        "dasha_data": state["dasha_data"],
        "yogas": state["yogas"],
    })
    # response = {"approved": True, "corrections": "optional notes"}
    return {
        "checkpoint_1_approved": response.get("approved", True),
        "checkpoint_1_corrections": response.get("corrections", ""),
    }


# ── Node: llm_call ────────────────────────────────────────────────────────────

def llm_call_node(state: AgentState) -> dict:
    """
    Call Claude with current context. Handles both initial synthesis and revisions.
    The LLM may call ask_human if it encounters ambiguous patterns.
    """
    model_name = state.get("llm_model") or os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5")
    api_key = os.getenv("OPENROUTER_API_KEY")
    log.info("llm_call_node: model=%s api_key_set=%s", model_name, bool(api_key))

    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        request_timeout=90,
    )
    llm_with_tools = llm.bind_tools(SYNTHESIS_TOOLS)

    messages = list(state.get("messages") or [])

    if not messages or not isinstance(messages[0], SystemMessage):
        # First call or continuation after tool use / revision — always prepend
        # system prompt + chart context so the LLM never loses its grounding.
        messages = [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(content=build_synthesis_message(state)),
        ] + messages

    log.info("llm_call_node: sending %d messages to LLM", len(messages))
    if log.isEnabledFor(logging.DEBUG):
        for i, m in enumerate(messages):
            log.debug("llm_call_node: msg[%d] type=%s content=%s",
                      i, type(m).__name__, getattr(m, "content", None))
    import time

    def _invoke(with_tools: bool):
        bound = llm.bind_tools(SYNTHESIS_TOOLS) if with_tools else llm
        return bound.invoke(messages)

    max_retries = 5
    use_tools = True
    for attempt in range(max_retries):
        try:
            response = _invoke(use_tools)
            log.info("llm_call_node: response content_len=%s tool_calls=%s tools_enabled=%s",
                     len(response.content) if response.content else 0,
                     [tc["name"] for tc in (response.tool_calls or [])],
                     use_tools)
            log.debug("llm_call_node: response content=%s tool_calls=%s",
                      response.content, response.tool_calls)
            return {"messages": [response]}
        except Exception as e:
            err = str(e)
            if ("400" in err or "tool_use_failed" in err) and use_tools:
                # Model can't handle tool calling — disable and retry immediately
                log.warning("llm_call_node: tool calling failed (model may not support it), retrying without tools")
                use_tools = False
            elif "402" in err or "insufficient" in err.lower() or "billing" in err.lower() or "no credits" in err.lower():
                log.error("llm_call_node: out of credits — %s", err)
                raise RuntimeError(
                    "OPENROUTER_OUT_OF_CREDITS: Your OpenRouter account has insufficient credits. "
                    "Please top up at openrouter.ai/credits."
                )
            elif ("429" in err or "rate" in err.lower() or "quota" in err.lower()) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5   # 5s, 10s, 20s, 40s
                log.warning("llm_call_node: 429 rate limit, retrying in %ds (attempt %d/%d)",
                            wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                log.error("llm_call_node: LLM call failed — %s: %s", type(e).__name__, e)
                raise


# ── Node: run_tools ───────────────────────────────────────────────────────────

def run_tools_node(state: AgentState) -> dict:
    """
    HITL Pattern 2 — Human-as-a-Tool.
    Execute tool calls from the LLM. If ask_human is called, interrupt() pauses
    execution and the UI collects the astrologer's answer before resuming.
    """
    messages = state.get("messages") or []
    last_msg = messages[-1]
    human_answers = list(state.get("human_answers") or [])

    tool_map = {t.name: t for t in SYNTHESIS_TOOLS}
    tool_results = []

    for tc in last_msg.tool_calls:
        log.debug("run_tools_node: tool=%s args=%s", tc["name"], tc["args"])
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            result = f"Unknown tool: {tc['name']}"
        else:
            # ask_human calls interrupt() internally — graph pauses here
            result = tool_fn.invoke(tc["args"])

            if tc["name"] == "ask_human":
                question = tc["args"].get("question", "")
                human_answers = human_answers + [{"question": question, "answer": result}]

        log.debug("run_tools_node: tool=%s result=%s", tc["name"], result)
        tool_results.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"])
        )

    return {
        "messages": tool_results,
        "human_answers": human_answers,
    }


# ── Node: checkpoint_2 ────────────────────────────────────────────────────────

def checkpoint_2_node(state: AgentState) -> dict:
    """
    HITL Pattern 1 — Approval Gate (second checkpoint).
    Extract draft brief from LLM messages and present to astrologer for review.
    Astrologer can approve or provide feedback for revision.

    HITL Pattern 3 — Iterative Refinement is triggered if feedback is given.
    """
    # Extract the final text content from the last LLM message as the draft
    messages = state.get("messages") or []
    draft = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if not content:
            continue
        # Content can be a plain string or a list of content blocks
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = "\n".join(parts).strip()
        else:
            text = ""
        log.info("checkpoint_2_node: msg type=%s content_type=%s text_len=%d",
                 type(msg).__name__, type(content).__name__, len(text))
        if text:
            draft = text
            break

    log.debug("checkpoint_2_node: draft=%s", draft)
    response = interrupt({
        "type": "checkpoint_2",
        "draft_brief": draft,
        "revision_count": state.get("revision_count", 0),
    })
    # response = {"approved": True} | {"approved": False, "feedback": "Please add..."}

    updates: dict = {
        "draft_brief": draft,
        "checkpoint_2_approved": response.get("approved", False),
    }
    if not response.get("approved"):
        updates["checkpoint_2_feedback"] = response.get("feedback", "")
        updates["revision_count"] = (state.get("revision_count") or 0) + 1
        # Reset human_answers so the revision pass gets a fresh ask_human budget.
        updates["human_answers"] = []
        # Append a HumanMessage so the LLM sees the revision request as the
        # latest turn in the conversation (natural assistant-turn signal).
        # build_synthesis_message does NOT duplicate this — it no longer embeds
        # the revision text so it only appears once, here at the end.
        updates["messages"] = [
            HumanMessage(
                content=(
                    f"The astrologer reviewed your brief and requests changes:\n\n"
                    f"{response.get('feedback', '')}\n\n"
                    "Please revise the consultation brief accordingly."
                )
            )
        ]

    return updates


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_llm(state: AgentState) -> Literal["run_tools", "checkpoint_2"]:
    """If the LLM made tool calls (and under caps), execute them. Otherwise checkpoint 2."""
    messages = state.get("messages") or []
    last_msg = messages[-1] if messages else None
    ask_human_count = len(state.get("human_answers") or [])

    # Count how many llm→tool cycles have happened (each ToolMessage is one cycle)
    from langchain_core.messages import ToolMessage
    tool_iterations = sum(1 for m in messages if isinstance(m, ToolMessage))

    if (last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls
            and ask_human_count < MAX_ASK_HUMAN
            and tool_iterations < MAX_LLM_ITERATIONS):
        return "run_tools"
    return "checkpoint_2"


def route_after_checkpoint_2(state: AgentState) -> Literal["llm_call", "__end__"]:
    """If approved, finish. If feedback given and under revision limit, revise."""
    if state.get("checkpoint_2_approved"):
        return "__end__"
    if (state.get("revision_count") or 0) >= MAX_REVISIONS:
        return "__end__"
    return "llm_call"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph(db_path: str = "jyotish.db"):
    """
    Build and compile the LangGraph agent with SQLite checkpointing.

    Args:
        db_path: Path to the SQLite file for state persistence.

    Returns:
        Compiled LangGraph graph ready to invoke.
    """
    graph = StateGraph(AgentState)

    graph.add_node("compute", compute_node)
    graph.add_node("checkpoint_1", checkpoint_1_node)
    graph.add_node("llm_call", llm_call_node)
    graph.add_node("run_tools", run_tools_node)
    graph.add_node("checkpoint_2", checkpoint_2_node)

    graph.set_entry_point("compute")
    graph.add_edge("compute", "checkpoint_1")
    graph.add_edge("checkpoint_1", "llm_call")

    graph.add_conditional_edges("llm_call", route_after_llm, {
        "run_tools": "run_tools",
        "checkpoint_2": "checkpoint_2",
    })
    graph.add_edge("run_tools", "llm_call")

    graph.add_conditional_edges("checkpoint_2", route_after_checkpoint_2, {
        "llm_call": "llm_call",
        "__end__": END,
    })

    import sqlite3
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)
