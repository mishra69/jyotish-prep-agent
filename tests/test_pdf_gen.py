"""
PDF generation end-to-end smoke test.

Computes a real birth chart, calls the LLM with our actual system prompt,
generates a PDF from the real LLM response, and writes it to
tests/output_test.pdf for manual review.

This tests both:
  - Whether the LLM honours our plain-text instructions
  - Whether _generate_pdf handles whatever the LLM actually produces

Usage:
    python -m tests.test_pdf_gen
    # or
    python tests/test_pdf_gen.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

# ── 1. Compute a real chart ───────────────────────────────────────────────────
# Jawaharlal Nehru: 14 Nov 1889, 23:36, Allahabad — stable, well-known data.

from agent.tools import tool_compute_chart, tool_compute_dasha, tool_compute_yogas

print("Computing chart...")
chart = tool_compute_chart.invoke({
    "client_name": "Test Client",
    "birth_date": "1889-11-14",
    "birth_time": "23:36",
    "birth_place": "Allahabad, India",
    "latitude": 25.4358,
    "longitude": 81.8463,
    "timezone": "Asia/Kolkata",
})
dasha = tool_compute_dasha.invoke({"birth_chart": chart})
yogas = tool_compute_yogas.invoke({"birth_chart": chart})

# ── 2. Build the exact same message the graph sends to the LLM ───────────────

from agent.prompts import SYNTHESIS_SYSTEM_PROMPT, build_synthesis_message

state = {
    "client_name": "Test Client",
    "birth_date": "1889-11-14",
    "birth_time": "23:36",
    "birth_place": "Allahabad, India",
    "latitude": 25.4358,
    "longitude": 81.8463,
    "timezone": "Asia/Kolkata",
    "client_topics": ["career"],
    "custom_topic": "",
    "client_questions": "Will I have a notable career in public service?",
    "birth_chart": chart,
    "dasha_data": dasha,
    "yogas": yogas,
    "checkpoint_1_corrections": "",
    "checkpoint_2_feedback": "",
    "revision_count": 0,
    "human_answers": [],
}

human_message = build_synthesis_message(state)

# ── 3. Call the LLM — no tools, just get the brief ───────────────────────────

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

model_name = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5")
api_key = os.getenv("OPENROUTER_API_KEY")

print(f"Calling LLM ({model_name})...")
llm = ChatOpenAI(
    model=model_name,
    temperature=0,
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
    request_timeout=120,
)

response = llm.invoke([
    SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
    HumanMessage(content=human_message),
])

brief = response.content if isinstance(response.content, str) else ""
print(f"\nLLM response ({len(brief)} chars):\n{'-'*60}")
print(brief)
print('-' * 60)

# ── 4. Check for known bad characters ────────────────────────────────────────

BAD_CHARS = {
    "**": "markdown bold",
    "##": "markdown heading",
    "->": "ascii arrow",
    "\u2192": "Unicode arrow →",
    "\u2726": "star ✦",
    "\u26a0": "warning ⚠",
    "\u2717": "cross ✗",
    "\u2550": "box drawing ═",
    "===": "triple equals",
}

issues = [(seq, label) for seq, label in BAD_CHARS.items() if seq in brief]
if issues:
    print("\nWARNING: LLM output contains problematic sequences:")
    for seq, label in issues:
        count = brief.count(seq)
        print(f"  {label!r:25s} ({count}x): {seq!r}")
else:
    print("\nOK: No known bad characters found in LLM output.")

# ── 5. Generate PDF ───────────────────────────────────────────────────────────

import unittest.mock as _mock
import importlib.util

sys.modules.setdefault("streamlit", _mock.MagicMock())

_spec = importlib.util.spec_from_file_location(
    "app_module",
    os.path.join(os.path.dirname(__file__), "..", "ui", "app.py"),
)
_mod = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_mod)
except Exception:
    pass

print("\nGenerating PDF...")
birth_info = "14 November 1889  23:36  -  Allahabad, India"
pdf_bytes = _mod._generate_pdf(chart, brief, "Test Client", birth_info)

out_path = os.path.join(os.path.dirname(__file__), "output_test.pdf")
with open(out_path, "wb") as f:
    f.write(pdf_bytes)

print(f"PDF written: {out_path}  ({len(pdf_bytes):,} bytes)")
print("Open to verify layout, alignment, and character rendering.")
