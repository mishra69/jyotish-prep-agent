import type { ChartApiResponse, Intake } from '../lib/types';
import { TOPIC_FOCUS } from './prompt-text';

export { SYNTHESIS_SYSTEM_PROMPT } from './prompt-text';

// Python str.format helpers: `{x:10s}` pads right, `{n:2d}` pads left.
const ljust = (s: unknown, n: number) => String(s).padEnd(n);
const rjust = (s: unknown, n: number) => String(s).padStart(n);
const day = (iso: string | undefined) => (iso ?? '').slice(0, 10);

/**
 * The user message for the synthesis call: chart data, topic guidance, the
 * client's questions, and the astrologer's corrections from chart review.
 *
 * Mirrors agent/prompts.py:build_synthesis_message character for character --
 * test/prompt.test.ts checks it against that function's real output. What the
 * LLM is sent should go through toAscii(); this function stays a faithful port
 * so the parity test can prove it.
 */
export function buildSynthesisMessageRaw(
  intake: Intake,
  api: Pick<ChartApiResponse, 'chart' | 'dasha' | 'yogas'>,
  corrections: string,
): string {
  const { chart, dasha, yogas } = api;

  let topics = intake.client_topics.filter(Boolean).map((t) => t.toLowerCase());
  if (topics.length === 0) topics = ['general'];

  const customTopic = intake.custom_topic.trim();
  let effectiveTopic = topics.join(', ');
  if (customTopic) effectiveTopic += ` (${customTopic})`;

  const topicFocusText = [...new Set(topics)]
    .map((t) => TOPIC_FOCUS[t] ?? TOPIC_FOCUS.general)
    .join('\n\n');

  const lines = [
    '=== BIRTH CHART DATA ===',
    `Client: ${intake.client_name}`,
    `Born: ${intake.birth_date} ${intake.birth_time}, ${intake.birth_place}`,
    `Topic: ${effectiveTopic}`,
    '',
    `Lagna (Ascendant): ${chart.lagna} at ${chart.lagna_degree.toFixed(1)}°`,
    `Moon: ${chart.moon_sign} (${chart.moon_nakshatra}, Pada ${chart.moon_nakshatra_pada})`,
    '',
    'PLANETARY POSITIONS (Whole Sign houses, sidereal/Lahiri):',
  ];

  for (const [planet, pos] of Object.entries(chart.planets)) {
    const retro = pos.retrograde ? ' (R)' : '';
    lines.push(
      `  ${ljust(planet, 10)} → ${ljust(pos.sign, 15)} House ${rjust(pos.house, 2)}  ${pos.nakshatra}${retro}`,
    );
  }

  lines.push('', 'HOUSE LORDS:');
  const houses = Object.entries(chart.houses).sort(([a], [b]) => Number(a) - Number(b));
  for (const [num, h] of houses) {
    lines.push(`  House ${rjust(Number(num), 2)} (${ljust(h.sign, 15)}) — Lord: ${h.lord}`);
  }

  const maha = dasha.current_mahadasha;
  const antar = dasha.current_antardasha;
  lines.push(
    '',
    'VIMSHOTTARI DASHA:',
    `  Mahadasha:  ${maha.planet}  (${day(maha.start_date)} → ${day(maha.end_date)})`,
    `  Antardasha: ${antar.planet}  (${day(antar.start_date)} → ${day(antar.end_date)})`,
    '  Upcoming transitions:',
  );
  for (const t of dasha.next_transitions) {
    lines.push(`    ${ljust(t.planet, 10)} ${day(t.start_date)} → ${day(t.end_date)}`);
  }

  lines.push('', 'YOGAS IDENTIFIED:');
  for (const y of yogas) {
    const marker = y.confidence === 'confirmed' ? '✦' : y.confidence === 'borderline' ? '⚠' : '✗';
    lines.push(`  ${marker} [${ljust(y.confidence, 10)}] ${y.name}`);
    lines.push(`             ${y.formation_details}`);
  }

  lines.push('', topicFocusText);

  const questions = intake.client_questions.trim();
  if (questions) {
    lines.push(
      '',
      "CLIENT'S SPECIFIC QUESTIONS:",
      questions,
      '(Address these directly in the SUGGESTED TALKING POINTS section)',
    );
  }

  const notes = corrections.trim();
  if (notes) {
    lines.push('', `ASTROLOGER CORRECTIONS/NOTES (from prep review):\n${notes}`);
  }

  return lines.join('\n');
}

// The system prompt demands plain ASCII output (the brief goes to PDF), so the
// template should not model the characters it forbids. Only the template's own
// decorations are replaced: user-entered text (a client named Śrī, a birth in
// Zürich) passes through untouched.
const TEMPLATE_DECORATIONS: Record<string, string> = {
  '✦': '+', // confirmed yoga
  '⚠': '?', // borderline yoga
  '✗': 'x', // not formed
  '→': '->',
  '—': '-',
  '–': '-',
  '°': ' deg',
};
const DECORATION_RE = new RegExp(`[${Object.keys(TEMPLATE_DECORATIONS).join('')}]`, 'g');

export function stripTemplateDecorations(text: string): string {
  return text.replace(DECORATION_RE, (ch) => TEMPLATE_DECORATIONS[ch]);
}

/**
 * What the LLM actually receives. The replacement runs over the whole message,
 * so a user field that happened to contain one of these seven symbols would be
 * converted too -- harmless (an arrow becomes "->"), and accented letters or
 * Devanagari are never touched.
 */
export function buildSynthesisMessage(
  intake: Intake,
  api: Pick<ChartApiResponse, 'chart' | 'dasha' | 'yogas'>,
  corrections: string,
): string {
  return stripTemplateDecorations(buildSynthesisMessageRaw(intake, api, corrections));
}
