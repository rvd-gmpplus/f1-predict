"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { predictionsApi } from "@/lib/api";
import type { PredictionSubmission } from "@/types";

export function useMyPrediction(raceId: number | null) {
  return useQuery({
    queryKey: ["myPrediction", raceId],
    queryFn: () => predictionsApi.getMine(raceId!),
    enabled: raceId !== null,
    retry: false, // 404 is expected when no prediction exists
  });
}

export function useSubmitPrediction(raceId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PredictionSubmission) =>
      predictionsApi.submit(raceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["myPrediction", raceId] });
    },
  });
}
