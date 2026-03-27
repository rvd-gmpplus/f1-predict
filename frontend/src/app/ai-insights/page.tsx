"use client";

import { useState } from "react";
import { useActiveRace, useAIPredictions, useRaces, useDrivers, useTeams } from "@/hooks/useRaces";
import { Card, CardTitle } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { ConfidenceEvolutionChart } from "@/components/charts/ConfidenceEvolutionChart";
import { getCategoryLabel, getStageLabel } from "@/lib/utils";
import type { PredictionCategory } from "@/types";

const categories: PredictionCategory[] = [
  "qualifying_top5",
  "race_top5",
  "fastest_lap",
  "constructor_points",
  "quickest_pitstop",
  "safety_car",
  "dnf",
  "tire_strategy",
];

export default function AIInsightsPage() {
  const { data: activeRace } = useActiveRace();
  const { data: allRaces } = useRaces({ season: 2026 });
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(null);

  const raceId = selectedRaceId ?? activeRace?.id ?? null;
  const { data: predictions, isLoading } = useAIPredictions(raceId);
  const { data: drivers = [] } = useDrivers();
  const { data: teams = [] } = useTeams();

  const [selectedCategory, setSelectedCategory] = useState<PredictionCategory>("qualifying_top5");

  // Available stages
  const availableStages = predictions
    ? [...new Set(predictions.map((p) => p.session_stage))]
    : [];

  const latestStage = ["quali", "fp3", "fp2", "fp1", "pre"].find((s) =>
    availableStages.includes(s as "pre" | "fp1" | "fp2" | "fp3" | "quali"),
  );

  const selectedRace = allRaces?.find((r) => r.id === raceId);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h1 className="text-3xl font-bold">AI Insights</h1>
        {allRaces && (
          <Select
            value={raceId ?? ""}
            onChange={(e) => setSelectedRaceId(Number(e.target.value))}
            className="w-auto"
          >
            {allRaces.map((race) => (
              <option key={race.id} value={race.id}>
                Round {race.round} &mdash; {race.name}
              </option>
            ))}
          </Select>
        )}
      </div>

      {selectedRace && (
        <div className="flex items-center gap-3">
          <Badge variant="info">{selectedRace.name}</Badge>
          {latestStage && (
            <Badge variant="success">
              Latest: {getStageLabel(latestStage)}
            </Badge>
          )}
          <span className="text-sm text-f1-muted">
            {availableStages.length} stage{availableStages.length !== 1 ? "s" : ""} of data
          </span>
        </div>
      )}

      {/* Confidence Evolution */}
      <Card>
        <CardTitle>Confidence Evolution</CardTitle>
        <p className="text-sm text-f1-muted mb-4">
          How the AI&apos;s confidence changed across weekend sessions
        </p>

        <Tabs
          tabs={categories.map((c) => ({ id: c, label: getCategoryLabel(c) }))}
          activeTab={selectedCategory}
          onTabChange={(id) => setSelectedCategory(id as PredictionCategory)}
        />

        <div className="mt-6">
          {isLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : predictions && predictions.length > 0 ? (
            <ConfidenceEvolutionChart
              predictions={predictions}
              category={selectedCategory}
            />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-f1-muted">
              No AI prediction data available for this race.
            </div>
          )}
        </div>
      </Card>

      {/* Current predictions overview */}
      {predictions && predictions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {categories
            .filter((cat) => predictions.some((p) => p.category === cat))
            .map((category) => {
              const catPreds = predictions
                .filter(
                  (p) =>
                    p.category === category &&
                    p.session_stage === latestStage,
                )
                .sort((a, b) => (a.position ?? 99) - (b.position ?? 99));

              const avgConfidence =
                catPreds.reduce((sum, p) => sum + p.confidence, 0) /
                (catPreds.length || 1);

              return (
                <Card key={category} hover>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-sm">
                      {getCategoryLabel(category)}
                    </h3>
                    <span
                      className={`text-xs font-mono ${
                        avgConfidence >= 0.7
                          ? "text-green-400"
                          : avgConfidence >= 0.4
                            ? "text-yellow-400"
                            : "text-f1-muted"
                      }`}
                    >
                      {(avgConfidence * 100).toFixed(0)}% avg
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {catPreds.slice(0, 5).map((pred, i) => {
                      const driver = pred.driver_id
                        ? drivers.find((d) => d.id === pred.driver_id)
                        : null;
                      const team = pred.team_id
                        ? teams.find((t) => t.id === pred.team_id)
                        : null;

                      return (
                        <div
                          key={i}
                          className="flex items-center justify-between text-sm"
                        >
                          <div className="flex items-center gap-2">
                            {pred.position && (
                              <span className="text-xs font-mono text-f1-muted w-5">
                                P{pred.position}
                              </span>
                            )}
                            <span>
                              {driver?.code ?? team?.short_name ?? "N/A"}
                            </span>
                          </div>
                          <div className="w-20 bg-f1-surface rounded-full h-1.5">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-f1-red to-orange-500"
                              style={{
                                width: `${pred.confidence * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              );
            })}
        </div>
      )}
    </div>
  );
}
