/**
 * The consultation flow, replacing agent/graph.py's LangGraph graph.
 *
 *   chart_review --approveChart--> [LLM loop] --> awaiting_answer --answer--> [LLM loop]
 *                                       |                                        |
 *                                       +-------------> draft_review <-----------+
 *                                                          |  |
 *                                    review(approved) <----+  +----> review(feedback) --> [LLM loop]
 *                                          |
 *                                        final
 *
 * LangGraph needed interrupt() because a Python process had to stay paused
 * while the astrologer typed. Here every pause is just the end of an HTTP
 * request: these functions take the stored record, run until the next human
 * step, and return the new record for the caller to save.
 */
import type { ChartApiResponse, Intake } from '../lib/types';
import type { AssistantMessage, ChatMessage, LlmCaller } from './llm';
import { SYNTHESIS_SYSTEM_PROMPT, buildSynthesisMessage } from './prompt';

// Same limits as agent/graph.py.
export const MAX_ASK_HUMAN = 2; // questions per synthesis pass (reset on revision)
export const MAX_TOOL_ROUNDS = 6; // tool results across the whole consultation
export const MAX_REVISIONS = 5;
/** Guard against a model that never stops calling tools within one request. */
const MAX_LLM_CALLS_PER_STEP = 8;

const LIMIT_REACHED = 'Question limit reached. Proceed with your best judgment and write the brief.';
const FEEDBACK_HEAD = 'The astrologer reviewed your brief and requests changes:\n\n';
const FEEDBACK_TAIL = '\n\nPlease revise the consultation brief accordingly.';

export type { Stage } from '../lib/types';
import type { Stage } from '../lib/types';

/**
 * One tool call from the latest assistant turn. ask_human calls wait for the
 * astrologer; anything else is answered on the spot (`automatic`). All of a
 * turn's results are sent together, in call order, once every one has an answer.
 */
export type PendingCall = { tool_call_id: string; question: string; answer?: string; automatic?: boolean };

export type Consultation = {
  stage: Stage;
  intake: Intake;
  /** Chart, dasha, yogas, and conventions from the chart API. */
  astro: ChartApiResponse;
  model: string;
  /** Astrologer's notes from chart review; part of every synthesis prompt. */
  corrections: string;
  /** Conversation after the system and synthesis messages, which are rebuilt per call. */
  messages: ChatMessage[];
  /** ask_human calls from the latest assistant turn, answered one at a time. */
  pending: PendingCall[];
  /** ask_human answers in the current synthesis pass. */
  questions_asked: number;
  draft: string;
  revision_count: number;
  /** Where the brief came from: this app's model, or pasted from an outside chatbot. */
  brief_source?: 'model' | 'pasted';
};

export type { TimelineEntry } from '../lib/types';
import type { TimelineEntry } from '../lib/types';

export class FlowError extends Error {
  constructor(readonly status: 400 | 409 | 502, message: string) {
    super(message);
  }
}

function expectStage(c: Consultation, ...stages: Stage[]) {
  if (!stages.includes(c.stage)) {
    throw new FlowError(409, `This consultation is at "${c.stage}", not ${stages.map((s) => `"${s}"`).join(' or ')}.`);
  }
}

export function newConsultation(intake: Intake, astro: ChartApiResponse, model: string): Consultation {
  return {
    stage: 'chart_review',
    intake,
    astro,
    model,
    corrections: '',
    messages: [],
    pending: [],
    questions_asked: 0,
    draft: '',
    revision_count: 0,
  };
}

/** Exactly what the LLM is sent. Also what the "copy prompt" fallback offers. */
export function conversationFor(c: Consultation): ChatMessage[] {
  return [
    { role: 'system', content: SYNTHESIS_SYSTEM_PROMPT },
    { role: 'user', content: buildSynthesisMessage(c.intake, c.astro, c.corrections) },
    ...c.messages,
  ];
}

const toolRounds = (c: Consultation) => c.messages.filter((m) => m.role === 'tool').length;

/**
 * The brief without the model's lead-in ("Now I'll prepare the brief: ---"),
 * which would otherwise land at the top of the PDF. The system prompt's format
 * starts at a CONSULTATION BRIEF line; without one, the text is kept whole.
 */
export function briefFrom(text: string): string {
  const start = text.search(/^CONSULTATION BRIEF\b/m);
  return start > 0 ? text.slice(start) : text;
}

function questionFrom(args: string): string {
  try {
    const q = (JSON.parse(args) as { question?: unknown }).question;
    if (typeof q === 'string' && q.trim()) return q.trim();
  } catch {
    // fall through
  }
  return '(The model asked a question but it could not be read.)';
}

/**
 * Run the model until it either asks the astrologer something or produces a
 * draft. Mutates nothing; returns the updated record.
 */
async function runModel(c0: Consultation, llm: LlmCaller): Promise<Consultation> {
  const c: Consultation = { ...c0, messages: [...c0.messages], pending: [] };

  for (let calls = 0; calls < MAX_LLM_CALLS_PER_STEP; calls++) {
    const limitReached = c.questions_asked >= MAX_ASK_HUMAN || toolRounds(c) >= MAX_TOOL_ROUNDS;
    const reply: AssistantMessage = await llm({
      model: c.model,
      messages: conversationFor(c),
      toolChoice: limitReached ? 'none' : 'auto',
    });
    c.messages.push(reply);

    const calls_ = reply.tool_calls ?? [];
    if (calls_.length === 0) {
      const text = (reply.content ?? '').trim();
      if (!text) throw new FlowError(502, 'The model returned an empty response. Try again or pick another model.');
      return { ...c, stage: 'draft_review', draft: briefFrom(text), brief_source: 'model' };
    }

    if (limitReached) {
      // The model ignored tool_choice "none". Every tool call needs a result
      // before the conversation can continue, so answer them and go again.
      //
      // The Python app instead jumped to draft review here, leaving the calls
      // unanswered: the draft was whatever text came earlier (possibly none),
      // and a later revision request would 400 on the dangling calls.
      for (const call of calls_) {
        c.messages.push({ role: 'tool', tool_call_id: call.id, content: LIMIT_REACHED });
      }
      continue;
    }

    c.pending = calls_.map((call) =>
      call.function.name === 'ask_human'
        ? { tool_call_id: call.id, question: questionFrom(call.function.arguments) }
        : { tool_call_id: call.id, question: '', answer: `Unknown tool: ${call.function.name}`, automatic: true },
    );
    if (c.pending.some((p) => p.answer === undefined)) return { ...c, stage: 'awaiting_answer' };

    // Nothing for the astrologer (only unknown tools): send the results, go again.
    c.messages.push(...toolResults(c.pending));
    c.pending = [];
  }
  throw new FlowError(502, 'The model kept calling tools without producing a brief. Try again or pick another model.');
}

const toolResults = (pending: PendingCall[]): ChatMessage[] =>
  pending.map((p) => ({ role: 'tool', tool_call_id: p.tool_call_id, content: p.answer! }));

/** The question the astrologer should answer next, if any. */
export const currentQuestion = (c: Consultation) => c.pending.find((p) => p.answer === undefined);

/**
 * The steps already behind the astrologer, oldest first, for looking back:
 * each question they answered, and each draft with the feedback that sent it
 * back. Read from the stored conversation, so it needs no extra bookkeeping
 * and works for consultations saved before it existed.
 *
 * The draft under review (or the final brief) is not here: it is `c.draft`.
 */
export function timeline(c: Consultation): TimelineEntry[] {
  const out: TimelineEntry[] = [];
  const questions = new Map<string, string>();
  const msgs = c.messages;
  for (let i = 0; i < msgs.length; i++) {
    const m = msgs[i];
    if (m.role === 'assistant') {
      for (const call of m.tool_calls ?? []) {
        if (call.function.name === 'ask_human') questions.set(call.id, questionFrom(call.function.arguments));
      }
      const text = (m.content ?? '').trim();
      const next = msgs[i + 1];
      // A draft is a tool-free reply. Only ones sent back are history; the
      // last one is the current draft.
      if (!m.tool_calls?.length && text && next?.role === 'user' && next.content.startsWith(FEEDBACK_HEAD)) {
        const body = next.content.slice(FEEDBACK_HEAD.length);
        const feedback = body.endsWith(FEEDBACK_TAIL) ? body.slice(0, -FEEDBACK_TAIL.length) : body;
        out.push({ kind: 'draft', draft: briefFrom(text), feedback });
      }
    } else if (m.role === 'tool') {
      const question = questions.get(m.tool_call_id);
      if (question !== undefined && m.content !== LIMIT_REACHED) out.push({ kind: 'qa', question, answer: m.content });
    }
  }
  // Answers to earlier questions in a turn that still has one open.
  for (const p of c.pending) {
    if (!p.automatic && p.answer !== undefined) out.push({ kind: 'qa', question: p.question, answer: p.answer });
  }
  return out;
}

export async function approveChart(c: Consultation, corrections: string, llm: LlmCaller): Promise<Consultation> {
  expectStage(c, 'chart_review');
  return runModel({ ...c, corrections: corrections.trim() }, llm);
}

export async function answerQuestion(c: Consultation, answer: string, llm: LlmCaller): Promise<Consultation> {
  expectStage(c, 'awaiting_answer');
  const text = answer.trim();
  if (!text) throw new FlowError(400, 'Answer cannot be empty.');

  const pending = c.pending.map((p) => ({ ...p }));
  const next = pending.find((p) => p.answer === undefined);
  if (!next) throw new FlowError(409, 'No question is waiting for an answer.');
  next.answer = text;

  const updated = { ...c, pending, questions_asked: c.questions_asked + 1 };
  if (pending.some((p) => p.answer === undefined)) return updated; // more questions this turn

  return runModel({ ...updated, messages: [...c.messages, ...toolResults(pending)], pending: [] }, llm);
}

export async function reviewDraft(
  c: Consultation,
  review: { approved: true } | { approved: false; feedback: string },
  llm: LlmCaller,
): Promise<Consultation> {
  expectStage(c, 'draft_review');
  if (review.approved) return { ...c, stage: 'final' };

  const feedback = review.feedback.trim();
  if (!feedback) throw new FlowError(400, 'Describe what should change.');
  if (c.revision_count >= MAX_REVISIONS) {
    // The Python app silently ended here with the unapproved draft as final.
    throw new FlowError(409, `Revision limit (${MAX_REVISIONS}) reached. Approve this draft or start a new consultation.`);
  }

  return runModel(
    {
      ...c,
      revision_count: c.revision_count + 1,
      questions_asked: 0, // fresh ask_human budget per revision, as in Python
      messages: [
        ...c.messages,
        {
          role: 'user',
          content: FEEDBACK_HEAD + feedback + FEEDBACK_TAIL,
        },
      ],
    },
    llm,
  );
}

// ── Fallback: hand the work to an outside chatbot ────────────────────────────

/**
 * The same system prompt and chart message the API path sends, as one block
 * to paste into Claude or ChatGPT. Built from conversationFor() so the two
 * paths cannot drift. A chat UI has no ask_human tool, so the model is told
 * to ask in its reply instead.
 */
export function chatPrompt(c: Consultation): string {
  const [system, user] = conversationFor(c);
  return [
    system.content,
    '',
    'NOTE: You are in a chat, not an app, so you cannot call ask_human. If you',
    'would have asked the astrologer something, ask it in your reply and wait',
    'for my answer before writing the brief.',
    '',
    '---',
    '',
    user.content,
  ].join('\n');
}

/** Accept a brief the astrologer wrote with an outside chatbot. Ends the consultation. */
export function acceptPastedBrief(c: Consultation, brief: string): Consultation {
  expectStage(c, 'chart_review', 'awaiting_answer', 'draft_review');
  const text = brief.trim();
  if (!text) throw new FlowError(400, 'Paste the brief first.');
  return { ...c, stage: 'final', draft: text, pending: [], brief_source: 'pasted' };
}
