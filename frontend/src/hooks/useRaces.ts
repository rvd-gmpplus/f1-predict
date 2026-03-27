"use client";

import { useQuery } from "@tanstack/react-query";
import { racesApi } from "@/lib/api";

export function useRaces(params?: { season?: number; status?: string }) {
  return useQuery({
    queryKey: ["races", params],
    queryFn: () => racesApi.list(params),
  });
}

export function useRace(raceId: number | null) {
  return useQuery({
    queryKey: ["race", raceId],
    queryFn: () => racesApi.get(raceId!),
    enabled: raceId !== null,
  });
}

export function useRaceResults(raceId: number | null) {
  return useQuery({
    queryKey: ["raceResults", raceId],
    queryFn: () => racesApi.getResults(raceId!),
    enabled: raceId !== null,
  });
}

export function useAIPredictions(raceId: number | null) {
  return useQuery({
    queryKey: ["aiPredictions", raceId],
    queryFn: () => racesApi.getAIPredictions(raceId!),
    enabled: raceId !== null,
  });
}

export function useDrivers() {
  return useQuery({
    queryKey: ["drivers"],
    queryFn: () => racesApi.getDrivers(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTeams() {
  return useQuery({
    queryKey: ["teams"],
    queryFn: () => racesApi.getTeams(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useActiveRace() {
  const { data: races, ...rest } = useRaces({ status: "active" });
  const activeRace = races?.[0] ?? null;

  // Fallback to next upcoming race if no active race
  const { data: upcomingRaces } = useRaces({ status: "upcoming" });
  const nextRace = activeRace ?? upcomingRaces?.[0] ?? null;

  return { data: nextRace, ...rest };
}
