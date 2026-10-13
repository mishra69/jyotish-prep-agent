// OpenRouter models offered in the UI. Ported from ui/app.py:OPENROUTER_MODELS.
//
// Slugs verified against https://openrouter.ai/api/v1/models on 2026-08-17; all
// support tool calling (required for ask_human). When adding one, check its
// supported_parameters: without "temperature", set sampling: false or every
// call will 400.

export type ModelOption = { id: string; label: string; sampling: boolean };

export const MODELS: ModelOption[] = [
  { id: 'anthropic/claude-opus-5', label: 'Claude Opus 5 (recommended)', sampling: true },
  { id: 'anthropic/claude-fable-5', label: 'Claude Fable 5 (most capable, $$)', sampling: false },
  { id: 'anthropic/claude-sonnet-5', label: 'Claude Sonnet 5 (balanced)', sampling: false },
  { id: 'anthropic/claude-haiku-4.5', label: 'Claude Haiku 4.5 (fast, cheap)', sampling: true },
  { id: 'openai/gpt-5.5', label: 'GPT-5.5 (balanced)', sampling: false },
  { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (balanced)', sampling: true },
  { id: 'x-ai/grok-4.6', label: 'Grok 4.6 (balanced)', sampling: true },
  { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro (open source, cheap)', sampling: true },
];

export const DEFAULT_MODEL = MODELS[0].id;

export const findModel = (id: string) => MODELS.find((m) => m.id === id);
