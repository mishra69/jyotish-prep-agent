// OpenRouter models offered in the UI. Keep in sync with ui/app.py:OPENROUTER_MODELS.
//
// Slugs verified against https://openrouter.ai/api/v1/models on 2026-10-12; all
// support tool calling (required for ask_human). When adding one, check its
// supported_parameters: without "temperature", set sampling: false or calls
// may 400. Most current Anthropic and OpenAI models no longer list it.

export type ModelOption = { id: string; label: string; sampling: boolean };

export const MODELS: ModelOption[] = [
  { id: 'anthropic/claude-opus-5.5', label: 'Claude Opus 5.5 (recommended)', sampling: false },
  { id: 'anthropic/claude-fable-5.1', label: 'Claude Fable 5.1 (most capable, $$)', sampling: false },
  { id: 'anthropic/claude-haiku-5.5', label: 'Claude Haiku 5.5 (fast, cheap)', sampling: false },
  { id: 'openai/gpt-6-astra', label: 'GPT-6 Astra ($$)', sampling: false },
  { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro', sampling: true },
  { id: 'moonshotai/kimi-k3', label: 'Kimi K3 (open weights)', sampling: true },
];

export const DEFAULT_MODEL = MODELS[0].id;

export const findModel = (id: string) => MODELS.find((m) => m.id === id);
