import { describe, expect, it } from 'vitest';
import fixture from './fixtures/prompt-parity.json';
import {
  type Consultation,
  FlowError,
  MAX_REVISIONS,
  answerQuestion,
  approveChart,
  briefFrom,
  currentQuestion,
  newConsultation,
  reviewDraft,
} from '../src/worker/flow';
import type { AssistantMessage, ChatMessage, LlmRequest } from '../src/worker/llm';
import type { ChartApiResponse, Intake } from '../src/lib/types';

const astro = fixture.api_response as unknown as ChartApiResponse;
const intake: Intake = {
  client_name: 'Priya S.', birth_date: '1990-03-15', birth_time: '14:32', birth_place: 'Bangalore',
  latitude: 12.9716, longitude: 77.5946, client_topics: ['career'], custom_topic: '', client_questions: '',
};

// ── Scripted fake model ──────────────────────────────────────────────────────

let callSeq = 0;
const say = (text: string): AssistantMessage => ({ role: 'assistant', content: text });
const ask = (...questions: string[]): AssistantMessage => ({
  role: 'assistant', content: null,
  tool_calls: questions.map((q) => ({ id: `call_${++callSeq}`, type: 'function', function: { name: 'ask_human', arguments: JSON.stringify({ question: q }) } })),
});
const callTool = (name: string): AssistantMessage => ({
  role: 'assistant', content: null,
  tool_calls: [{ id: `call_${++callSeq}`, type: 'function', function: { name, arguments: '{}' } }],
});

/** Every tool call must be followed by exactly its results, in order -- providers 400 otherwise. */
function assertValidConversation(messages: ChatMessage[]) {
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === 'assistant' && m.tool_calls?.length) {
      const results = messages.slice(i + 1, i + 1 + m.tool_calls.length);
      expect(results.map((r) => (r.role === 'tool' ? r.tool_call_id : `<${r.role}>`))).toEqual(m.tool_calls.map((c) => c.id));
    }
    if (m.role === 'tool') {
      const prev = messages.slice(0, i).reverse().find((x) => x.role !== 'tool');
      expect(prev?.role, 'tool result must follow an assistant tool call').toBe('assistant');
    }
  }
}

function script(...replies: AssistantMessage[]) {
  const requests: LlmRequest[] = [];
  const llm = async (req: LlmRequest) => {
    assertValidConversation(req.messages);
    requests.push(structuredClone(req));
    const next = replies.shift();
    if (!next) throw new Error('fake model: no scripted reply left');
    return next;
  };
  return { llm, requests, remaining: () => replies.length };
}

const start = () => newConsultation(intake, astro, 'anthropic/claude-opus-5');

async function expectFlowError(p: Promise<unknown>, status: number, text?: RegExp) {
  const e = await p.then(() => null, (err) => err);
  expect(e).toBeInstanceOf(FlowError);
  expect((e as FlowError).status).toBe(status);
  if (text) expect((e as FlowError).message).toMatch(text);
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('happy paths', () => {
  it('chart approval with no questions goes straight to a draft', async () => {
    const m = script(say('CONSULTATION BRIEF\n...'));
    const c = await approveChart(start(), '  time may be +/- 10 min  ', m.llm);
    expect(c.stage).toBe('draft_review');
    expect(c.draft).toBe('CONSULTATION BRIEF\n...');
    expect(c.corrections).toBe('time may be +/- 10 min');
    const [sys, user] = m.requests[0].messages;
    expect(sys.role).toBe('system');
    expect(user.role === 'user' && user.content).toContain('ASTROLOGER CORRECTIONS/NOTES (from prep review):\ntime may be +/- 10 min');
    expect(m.requests[0].toolChoice).toBe('auto');
  });

  it('a question pauses the flow, and the answer resumes it', async () => {
    const m = script(ask('Is Gajakesari borderline here?'), say('BRIEF'));
    let c = await approveChart(start(), '', m.llm);
    expect(c.stage).toBe('awaiting_answer');
    expect(currentQuestion(c)?.question).toBe('Is Gajakesari borderline here?');

    c = await answerQuestion(c, 'Include it, flagged.', m.llm);
    expect(c.stage).toBe('draft_review');
    expect(c.questions_asked).toBe(1);
    const toolMsg = m.requests[1].messages.at(-1)!;
    expect(toolMsg).toMatchObject({ role: 'tool', content: 'Include it, flagged.' });
  });

  it('approving a draft makes it final', async () => {
    const m = script(say('BRIEF'));
    const c = await reviewDraft(await approveChart(start(), '', m.llm), { approved: true }, m.llm);
    expect(c.stage).toBe('final');
    expect(c.draft).toBe('BRIEF');
  });
});

describe('questions', () => {
  it('two questions in one turn are asked one at a time, then sent together', async () => {
    const m = script(ask('Q1', 'Q2'), say('BRIEF'));
    let c = await approveChart(start(), '', m.llm);
    c = await answerQuestion(c, 'A1', m.llm);
    expect(c.stage).toBe('awaiting_answer');
    expect(currentQuestion(c)?.question).toBe('Q2');
    expect(m.requests).toHaveLength(1); // no model call between the two answers

    c = await answerQuestion(c, 'A2', m.llm);
    expect(c.stage).toBe('draft_review');
    expect(m.requests[1].messages.slice(-2).map((x) => x.role === 'tool' && x.content)).toEqual(['A1', 'A2']);
  });

  it('after 2 answers the model is told not to call tools', async () => {
    const m = script(ask('Q1'), ask('Q2'), say('BRIEF'));
    let c = await approveChart(start(), '', m.llm);
    c = await answerQuestion(c, 'A1', m.llm);
    c = await answerQuestion(c, 'A2', m.llm);
    expect(c.stage).toBe('draft_review');
    expect(m.requests.map((r) => r.toolChoice)).toEqual(['auto', 'auto', 'none']);
  });

  it('if the model ignores the limit, its calls are answered and it is asked again', async () => {
    const m = script(ask('Q1'), ask('Q2'), ask('Q3 despite the limit'), say('BRIEF'));
    let c = await approveChart(start(), '', m.llm);
    c = await answerQuestion(c, 'A1', m.llm);
    c = await answerQuestion(c, 'A2', m.llm);
    expect(c.stage).toBe('draft_review');
    expect(c.draft).toBe('BRIEF');
    expect(m.requests[3].messages.at(-1)).toMatchObject({ role: 'tool', content: expect.stringMatching(/limit reached/i) });
  });

  it('an unknown tool next to a question keeps its result, in order', async () => {
    const mixed: AssistantMessage = {
      role: 'assistant', content: null,
      tool_calls: [...callTool('web_search').tool_calls!, ...ask('Q1').tool_calls!],
    };
    const m = script(mixed, say('BRIEF'));
    let c = await approveChart(start(), '', m.llm);
    expect(currentQuestion(c)?.question).toBe('Q1');
    c = await answerQuestion(c, 'A1', m.llm);
    expect(c.questions_asked).toBe(1); // the unknown tool is not a question
    expect(m.requests[1].messages.slice(-2).map((x) => x.role === 'tool' && x.content)).toEqual(['Unknown tool: web_search', 'A1']);
  });

  it('only unknown tools: answered automatically without stopping', async () => {
    const m = script(callTool('web_search'), say('BRIEF'));
    const c = await approveChart(start(), '', m.llm);
    expect(c.stage).toBe('draft_review');
  });
});

describe('revisions', () => {
  it('feedback is appended verbatim and the question budget resets', async () => {
    const m = script(ask('Q1'), say('DRAFT 1'), ask('Q after revision'), say('DRAFT 2'));
    let c = await approveChart(start(), '', m.llm);
    c = await answerQuestion(c, 'A1', m.llm);
    c = await reviewDraft(c, { approved: false, feedback: '  More on 10th lord.  ' }, m.llm);
    expect(c.revision_count).toBe(1);
    expect(c.stage).toBe('awaiting_answer'); // could ask again: budget was reset
    expect(c.questions_asked).toBe(0);
    expect(m.requests[2].messages.at(-1)).toEqual({
      role: 'user',
      content: 'The astrologer reviewed your brief and requests changes:\n\nMore on 10th lord.\n\nPlease revise the consultation brief accordingly.',
    });
    c = await answerQuestion(c, 'yes', m.llm);
    expect(c.draft).toBe('DRAFT 2');
  });

  it(`refuses a revision beyond ${MAX_REVISIONS} instead of silently finalizing`, async () => {
    const c: Consultation = { ...start(), stage: 'draft_review', draft: 'D', revision_count: MAX_REVISIONS };
    await expectFlowError(reviewDraft(c, { approved: false, feedback: 'again' }, script().llm), 409, /limit/);
  });
});

describe('guards', () => {
  it('actions in the wrong stage are 409', async () => {
    await expectFlowError(answerQuestion(start(), 'x', script().llm), 409);
    await expectFlowError(reviewDraft(start(), { approved: true }, script().llm), 409);
  });

  it('empty answer or feedback is 400', async () => {
    const m = script(ask('Q1'), say('BRIEF'));
    const c = await approveChart(start(), '', m.llm);
    await expectFlowError(answerQuestion(c, '   ', m.llm), 400);
    const d: Consultation = { ...start(), stage: 'draft_review', draft: 'D' };
    await expectFlowError(reviewDraft(d, { approved: false, feedback: ' ' }, m.llm), 400);
  });

  it('an empty model reply is an error, not an empty brief', async () => {
    await expectFlowError(approveChart(start(), '', script(say('   ')).llm), 502, /empty/);
  });

  it('a model that never stops calling tools is cut off', async () => {
    const m = script(...Array.from({ length: 20 }, () => callTool('web_search')));
    await expectFlowError(approveChart(start(), '', m.llm), 502, /kept calling tools/);
  });

  it('does not mutate the record it was given', async () => {
    const c0 = start();
    const before = structuredClone(c0);
    await approveChart(c0, 'notes', script(ask('Q1')).llm);
    expect(c0).toEqual(before);
  });
});

describe('brief extraction', () => {
  it("drops the model's lead-in before the CONSULTATION BRIEF heading", () => {
    expect(briefFrom("Now I'll prepare the consultation brief:\n\n---\n\nCONSULTATION BRIEF\nClient: X")).toBe('CONSULTATION BRIEF\nClient: X');
  });
  it('keeps the text whole when there is no heading', () => {
    expect(briefFrom('Something else entirely')).toBe('Something else entirely');
  });
  it('only matches the heading at the start of a line', () => {
    const t = 'Intro mentions CONSULTATION BRIEF mid-sentence.\nBody';
    expect(briefFrom(t)).toBe(t);
  });
  it('is applied to drafts from the model', async () => {
    const c = await approveChart(start(), '', script(say('Sure, here it is:\nCONSULTATION BRIEF\nX')).llm);
    expect(c.draft).toBe('CONSULTATION BRIEF\nX');
  });
});
