"use client";

import { useQuery } from "@tanstack/react-query";
import { leaderboardApi, usersApi } from "@/lib/api";

export function useSeasonLeaderboard() {
  return useQuery({
    queryKey: ["leaderboard", "season"],
    queryFn: () => leaderboardApi.season(),
  });
}

export function useRaceLeaderboard(raceId: number | null) {
  return useQuery({
    queryKey: ["leaderboard", "race", raceId],
    queryFn: () => leaderboardApi.race(raceId!),
    enabled: raceId !== null,
  });
}

export function useUserHistory(userId: number | null) {
  return useQuery({
    queryKey: ["userHistory", userId],
    queryFn: () => usersApi.history(userId!),
    enabled: userId !== null,
  });
}

export function useUserStats(userId: number | null) {
  return useQuery({
    queryKey: ["userStats", userId],
    queryFn: () => usersApi.stats(userId!),
    enabled: userId !== null,
  });
}
