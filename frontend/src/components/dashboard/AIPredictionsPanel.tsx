"use client";

import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { getStageLabel, getCategoryLabel } from "@/lib/utils";
import type { MLPrediction, Driver, Team } from "@/types";
import { useMemo } from "react";

interface AIPredictionsPanelProps {
  predictions: MLPrediction[];
  drivers: Driver[];
  teams: Team[];
}

export function AIPredictionsPanel({
  predictions,
  drivers,
  teams,
}: AIPredictionsPanelProps) {
  const driverMap = useMemo(
    () => new Map(drivers.map((d) => [d.id, d])),
    [drivers],
  );
  const teamMap = useMemo(
    () => new Map(teams.map((t) => [t.id, t])),
    [teams],
  );

  // Get the latest stage available
  const stages = ["quali", "fp3", "fp2", "fp1", "pre"];
  const latestStage = stages.find((s) =>
    predictions.some((p) => p.session_stage === s),
  );
  const latestPredictions = predictions.filter(
    (p) => p.session_stage === latestStage,
  );

  // Group by category
  const grouped = latestPredictions.reduce(
    (acc, pred) => {
      if (!acc[pred.category]) acc[pred.category] = [];
      acc[pred.category].push(pred);
      return acc;
    },
    {} as Record<string, MLPrediction[]>,
  );

  if (predictions.length === 0) {
    return (
      <Card>
        <CardTitle>AI Predictions</CardTitle>
        <p className="text-f1-muted text-sm">
          No AI predictions available yet. Check back closer to the race weekend.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <CardTitle>AI Predictions</CardTitle>
        {latestStage && (
          <Badge variant="info">{getStageLabel(latestStage)}</Badge>
        )}
      </div>

      <div className="space-y-4">
        {Object.entries(grouped)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([category, preds]) => (
            <div key={category}>
              <h4 className="text-xs font-medium text-f1-muted uppercase tracking-wider mb-2">
                {getCategoryLabel(category)}
              </h4>
              <div className="space-y-1">
                {preds
                  .sort((a, b) => (a.position ?? 99) - (b.position ?? 99))
                  .map((pred, i) => {
                    const driver = pred.driver_id
                      ? driverMap.get(pred.driver_id)
                      : null;
                    const team = pred.team_id
                      ? teamMap.get(pred.team_id)
                      : null;

                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-f1-surface/50"
                      >
                        <div className="flex items-center gap-3">
                          {pred.position && (
                            <span className="text-xs font-mono text-f1-muted w-4">
                              P{pred.position}
                            </span>
                          )}
                          {driver && (
                            <span className="text-sm font-medium">
                              <span
                                className="inline-block w-1 h-4 rounded-full mr-2 align-middle"
                                style={{
                                  backgroundColor:
                                    team?.color_hex ?? "#666",
                                }}
                              />
                              {driver.code}
                              <span className="text-f1-muted ml-1">
                                {driver.full_name}
                              </span>
                            </span>
                          )}
                          {team && !driver && (
                            <span className="text-sm font-medium">
                              <span
                                className="inline-block w-1 h-4 rounded-full mr-2 align-middle"
                                style={{ backgroundColor: team.color_hex }}
                              />
                              {team.name}
                            </span>
                          )}
                          {pred.value && !driver && !team && (
                            <span className="text-sm">{pred.value}</span>
                          )}
                        </div>
                        <div className="text-xs font-mono">
                          <span
                            className={
                              pred.confidence >= 0.7
                                ? "text-green-400"
                                : pred.confidence >= 0.4
                                  ? "text-yellow-400"
                                  : "text-f1-muted"
                            }
                          >
                            {(pred.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
      </div>
    </Card>
  );
}
