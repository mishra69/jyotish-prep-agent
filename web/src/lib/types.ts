// Shapes shared by the UI and the Worker.

// ── Chart API (api/main.py) ──────────────────────────────────────────────────

export type PlanetPosition = {
  planet: string;
  sign: string;
  degree: number;
  abs_degree: number;
  house: number;
  nakshatra: string;
  nakshatra_pada: number;
  retrograde: boolean;
};

export type House = { number: number; sign: string; lord: string };

export type Chart = {
  birth_datetime: string;
  latitude: number;
  longitude: number;
  timezone: string;
  lagna: string;
  lagna_degree: number;
  moon_sign: string;
  moon_nakshatra: string;
  moon_nakshatra_pada: number;
  planets: Record<string, PlanetPosition>;
  houses: Record<string, House>;
};

export type DashaNode = {
  planet: string;
  start_date: string;
  end_date: string;
  level: number;
  sub_dashas: DashaNode[];
};

export type Dasha = {
  current_mahadasha: DashaNode;
  current_antardasha: DashaNode;
  next_transitions: DashaNode[];
  mahadashas: DashaNode[];
};

export type YogaConfidence = 'confirmed' | 'borderline' | 'not_formed';

export type Yoga = {
  name: string;
  sanskrit_name: string;
  confidence: YogaConfidence;
  planets_involved: string[];
  description: string;
  formation_details: string;
};

export type ChartApiResponse = {
  meta: { api_version: string; timezone: string; ayanamsa: string; house_system: string; zodiac: string };
  chart: Chart;
  dasha: Dasha;
  yogas: Yoga[];
};

// ── Consultation ─────────────────────────────────────────────────────────────

export type Intake = {
  client_name: string;
  birth_date: string; // YYYY-MM-DD
  birth_time: string; // HH:MM
  birth_place: string;
  latitude: number;
  longitude: number;
  client_topics: string[];
  custom_topic: string;
  client_questions: string;
};

export type Stage = 'chart_review' | 'awaiting_answer' | 'draft_review' | 'final';

/** What GET /api/consultations/:id returns (src/worker/index.ts:view). */
export type ConsultationView = {
  id: string;
  stage: Stage;
  intake: Intake;
  astro: ChartApiResponse;
  model: string;
  corrections: string;
  question: string | null;
  questions_asked: number;
  max_questions: number;
  draft: string;
  brief_source: 'model' | 'pasted' | null;
  revision_count: number;
  max_revisions: number;
};

export type ConsultationSummary = {
  id: string;
  client_name: string;
  stage: Stage;
  created_at: number;
  updated_at: number;
};

export type Place = { label: string; latitude: number; longitude: number };
