import { describe, expect, it } from 'vitest';
import fixture from './fixtures/prompt-parity.json';
import {
  SYNTHESIS_SYSTEM_PROMPT,
  buildSynthesisMessage,
  buildSynthesisMessageRaw,
  stripTemplateDecorations,
} from '../src/worker/prompt';
import type { ChartApiResponse, Intake } from '../src/lib/types';

// Generated from agent/prompts.py against real chart API output.
const api = fixture.api_response as unknown as ChartApiResponse;

function split(intake: (typeof fixture.cases)[number]['intake']) {
  const { checkpoint_1_corrections, ...rest } = intake;
  return { intake: { ...rest, latitude: 12.9716, longitude: 77.5946 } as Intake, corrections: checkpoint_1_corrections };
}

describe('parity with agent/prompts.py', () => {
  it('system prompt is identical', () => {
    expect(SYNTHESIS_SYSTEM_PROMPT).toBe(fixture.system_prompt);
  });

  it.each(fixture.cases.map((c, i) => [i, c] as const))('case %i: user message is identical', (_i, c) => {
    const { intake, corrections } = split(c.intake);
    expect(buildSynthesisMessageRaw(intake, api, corrections)).toBe(c.expected);
  });
});

describe('what the LLM receives', () => {
  it('contains no template decorations, so it no longer models forbidden output', () => {
    for (const c of fixture.cases) {
      const { intake, corrections } = split(c.intake);
      expect(buildSynthesisMessage(intake, api, corrections)).toMatch(/^[\x00-\x7F]*$/);
    }
  });

  it('differs from the Python output only by the decoration substitutions', () => {
    const { intake, corrections } = split(fixture.cases[0].intake);
    expect(buildSynthesisMessage(intake, api, corrections)).toBe(
      stripTemplateDecorations(fixture.cases[0].expected),
    );
  });

  it('keeps yoga confidence readable after substitution', () => {
    const { intake, corrections } = split(fixture.cases[0].intake);
    const msg = buildSynthesisMessage(intake, api, corrections);
    expect(msg).toContain('+ [confirmed ]');
    expect(msg).toContain('x [not_formed]');
  });

  it('leaves user-entered non-ASCII text untouched', () => {
    const { intake, corrections } = split(fixture.cases[1].intake);
    const msg = buildSynthesisMessage(
      { ...intake, client_name: 'Śrī Devī', birth_place: 'Zürich', client_questions: 'करियर?' },
      api,
      corrections,
    );
    expect(msg).toContain('Client: Śrī Devī');
    expect(msg).toContain('Zürich');
    expect(msg).toContain('करियर?');
  });
});
