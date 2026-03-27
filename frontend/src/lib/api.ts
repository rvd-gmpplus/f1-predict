import { getToken, removeToken } from "./auth";
import type {
  RegisterRequest,
  LoginRequest,
  TokenResponse,
  User,
  Team,
  Driver,
  RaceWeekend,
  RaceWeekendDetail,
  MLPrediction,
  PredictionSubmission,
  PredictionResponse,
  RaceResults,
  LeaderboardEntry,
  UserHistory,
  UserStats,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Base Fetch ──────────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    if (res.status === 401) {
      removeToken();
    }
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }

  return res.json();
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  register(data: RegisterRequest): Promise<TokenResponse> {
    return fetchApi<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  login(data: LoginRequest): Promise<TokenResponse> {
    return fetchApi<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  me(): Promise<User> {
    return fetchApi<User>("/auth/me");
  },

  getGoogleLoginUrl(): string {
    return `${API_URL}/auth/google`;
  },

  getGitHubLoginUrl(): string {
    return `${API_URL}/auth/github`;
  },
};

// ─── Races ───────────────────────────────────────────────────────────────────

export const racesApi = {
  list(params?: { season?: number; status?: string }): Promise<RaceWeekend[]> {
    const searchParams = new URLSearchParams();
    if (params?.season) searchParams.set("season", String(params.season));
    if (params?.status) searchParams.set("status", params.status);
    const qs = searchParams.toString();
    return fetchApi<RaceWeekend[]>(`/races${qs ? `?${qs}` : ""}`);
  },

  get(raceId: number): Promise<RaceWeekendDetail> {
    return fetchApi<RaceWeekendDetail>(`/races/${raceId}`);
  },

  getResults(raceId: number): Promise<RaceResults> {
    return fetchApi<RaceResults>(`/races/${raceId}/results`);
  },

  getAIPredictions(raceId: number): Promise<MLPrediction[]> {
    return fetchApi<MLPrediction[]>(`/races/${raceId}/ai-predictions`);
  },

  getDrivers(): Promise<Driver[]> {
    return fetchApi<Driver[]>("/races/drivers/all");
  },

  getTeams(): Promise<Team[]> {
    return fetchApi<Team[]>("/races/teams/all");
  },
};

// ─── Predictions ─────────────────────────────────────────────────────────────

export const predictionsApi = {
  submit(raceId: number, data: PredictionSubmission): Promise<PredictionResponse> {
    return fetchApi<PredictionResponse>(`/races/${raceId}/predict`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getMine(raceId: number): Promise<PredictionResponse> {
    return fetchApi<PredictionResponse>(`/races/${raceId}/my-prediction`);
  },
};

// ─── Leaderboard ─────────────────────────────────────────────────────────────

export const leaderboardApi = {
  season(): Promise<LeaderboardEntry[]> {
    return fetchApi<LeaderboardEntry[]>("/leaderboard/season");
  },

  race(raceId: number): Promise<LeaderboardEntry[]> {
    return fetchApi<LeaderboardEntry[]>(`/leaderboard/race/${raceId}`);
  },
};

// ─── Users ───────────────────────────────────────────────────────────────────

export const usersApi = {
  history(userId: number): Promise<UserHistory> {
    return fetchApi<UserHistory>(`/users/${userId}/history`);
  },

  stats(userId: number): Promise<UserStats> {
    return fetchApi<UserStats>(`/users/${userId}/stats`);
  },
};

export { ApiError };
