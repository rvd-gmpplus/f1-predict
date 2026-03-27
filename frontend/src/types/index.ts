// ─── Auth ────────────────────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  username: string;
  avatar_url: string | null;
  total_score: number;
}

// ─── F1 Data ─────────────────────────────────────────────────────────────────

export interface Team {
  id: number;
  name: string;
  short_name: string;
  color_hex: string;
  country: string;
}

export interface Driver {
  id: number;
  code: string;
  full_name: string;
  team_id: number;
  number: number;
  country: string;
}

export interface RaceWeekend {
  id: number;
  season: number;
  round: number;
  name: string;
  circuit_id: string;
  country: string;
  is_sprint_weekend: boolean;
  quali_time: string | null;
  race_time: string | null;
  prediction_deadline: string | null;
  status: "upcoming" | "active" | "completed";
}

export interface MLPrediction {
  category: PredictionCategory;
  position: number | null;
  driver_id: number | null;
  team_id: number | null;
  confidence: number;
  session_stage: SessionStage;
  generated_at: string;
}

export interface RaceWeekendDetail extends RaceWeekend {
  ai_predictions: MLPrediction[];
}

// ─── Predictions ─────────────────────────────────────────────────────────────

export type PredictionCategory =
  | "qualifying_top5"
  | "race_top5"
  | "sprint_top5"
  | "fastest_lap"
  | "constructor_points"
  | "quickest_pitstop"
  | "teammate_battle"
  | "safety_car"
  | "dnf"
  | "tire_strategy";

export type SessionStage = "pre" | "fp1" | "fp2" | "fp3" | "quali";

export interface PredictionDetailInput {
  category: PredictionCategory;
  position?: number | null;
  driver_id?: number | null;
  team_id?: number | null;
  value?: string | null;
}

export interface PredictionSubmission {
  details: PredictionDetailInput[];
}

export interface PredictionDetailResponse {
  category: PredictionCategory;
  position: number | null;
  driver_id: number | null;
  team_id: number | null;
  value: string | null;
}

export interface PredictionResponse {
  id: number;
  race_weekend_id: number;
  submitted_at: string;
  locked: boolean;
  details: PredictionDetailResponse[];
}

// ─── Scoring ─────────────────────────────────────────────────────────────────

export interface ScoreDetail {
  category: PredictionCategory;
  points_earned: number;
  breakdown: Record<string, unknown> | null;
}

export interface RaceResults {
  race_weekend_id: number;
  user_scores: ScoreDetail[];
  total_points: number;
}

// ─── Leaderboard ─────────────────────────────────────────────────────────────

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  username: string;
  total_score: number;
  races_participated: number;
  best_weekend: number;
  is_ai: boolean;
}

// ─── User Stats ──────────────────────────────────────────────────────────────

export interface UserHistory {
  user_id: number;
  username: string;
  races: Array<{
    race_weekend_id: number;
    points: number;
  }>;
}

export interface CategoryStat {
  category: PredictionCategory;
  total_points: number;
  predictions_made: number;
  avg_points: number;
}

export interface UserStats {
  user_id: number;
  username: string;
  total_score: number;
  races_participated: number;
  categories: CategoryStat[];
  best_category: PredictionCategory | null;
  worst_category: PredictionCategory | null;
}
