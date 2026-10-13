import { findModel } from '../lib/models';
import askHumanTool from './ask-human-tool.json';

// OpenAI-compatible chat messages, as OpenRouter accepts them.
export type ToolCall = { id: string; type: 'function'; function: { name: string; arguments: string } };
export type ChatMessage =
  | { role: 'system' | 'user'; content: string }
  | { role: 'assistant'; content: string | null; tool_calls?: ToolCall[] }
  | { role: 'tool'; tool_call_id: string; content: string };

export type AssistantMessage = Extract<ChatMessage, { role: 'assistant' }>;

export type LlmRequest = {
  model: string;
  messages: ChatMessage[];
  /** 'none' forbids tool calls this turn while keeping the definitions, which
   * providers need when the history already contains tool calls. */
  toolChoice: 'auto' | 'none';
};

export type LlmCaller = (req: LlmRequest) => Promise<AssistantMessage>;

/** Errors the astrologer can act on, with a message fit to show them. */
export class LlmError extends Error {
  constructor(
    readonly kind: 'auth' | 'credits' | 'rate_limited' | 'bad_request' | 'upstream' | 'timeout',
    message: string,
  ) {
    super(message);
  }
}

const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';
const TIMEOUT_MS = 120_000;
const RETRY_DELAYS_MS = [5_000, 15_000];

export const TOOLS = [askHumanTool];

export function openRouterCaller(apiKey: string, sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))): LlmCaller {
  return async ({ model, messages, toolChoice }) => {
    // Reasoning models reject sampling params with a 400. In the Python app that
    // 400 was misread as "no tool support" and tools were silently dropped; here
    // the param is simply omitted, and any 400 surfaces as an error.
    const sampling = findModel(model)?.sampling ?? true;
    const body = JSON.stringify({
      model,
      messages,
      tools: TOOLS,
      tool_choice: toolChoice,
      ...(sampling ? { temperature: 0 } : {}),
    });

    for (let attempt = 0; ; attempt++) {
      let res: Response;
      try {
        res = await fetch(OPENROUTER_URL, {
          method: 'POST',
          headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
          body,
          signal: AbortSignal.timeout(TIMEOUT_MS),
        });
      } catch (e) {
        if ((e as Error).name === 'TimeoutError') throw new LlmError('timeout', 'The model took too long to respond. Try again.');
        if (attempt < RETRY_DELAYS_MS.length) { await sleep(RETRY_DELAYS_MS[attempt]); continue; }
        throw new LlmError('upstream', `Could not reach OpenRouter: ${(e as Error).message}`);
      }

      if (res.ok) {
        const json = (await res.json()) as { choices?: { message: AssistantMessage }[]; error?: { message?: string } };
        // OpenRouter can return 200 with an error body when the provider fails.
        const msg = json.choices?.[0]?.message;
        if (!msg) throw new LlmError('upstream', `Model returned no message: ${json.error?.message ?? 'unknown error'}`);
        return { role: 'assistant', content: msg.content ?? null, ...(msg.tool_calls?.length ? { tool_calls: msg.tool_calls } : {}) };
      }

      const detail = await res.text().catch(() => '');
      if (res.status === 401) throw new LlmError('auth', 'OpenRouter rejected the API key. Generate a new one at openrouter.ai/keys.');
      if (res.status === 402) throw new LlmError('credits', 'OpenRouter credits or spending limit reached. Top up or raise the limit at openrouter.ai.');
      if ((res.status === 429 || res.status >= 500) && attempt < RETRY_DELAYS_MS.length) {
        await sleep(RETRY_DELAYS_MS[attempt]);
        continue;
      }
      if (res.status === 429) throw new LlmError('rate_limited', 'The model is rate limited right now. Wait a minute and try again.');
      if (res.status === 400) throw new LlmError('bad_request', `The model rejected the request: ${detail.slice(0, 300)}`);
      throw new LlmError('upstream', `OpenRouter error ${res.status}: ${detail.slice(0, 300)}`);
    }
  };
}
