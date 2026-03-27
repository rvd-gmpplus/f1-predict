"use client";

import { useAuth } from "@/hooks/useAuth";
import { useUserHistory, useUserStats } from "@/hooks/useLeaderboard";
import { useRaces } from "@/hooks/useRaces";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { AccuracyOverTimeChart } from "@/components/charts/AccuracyOverTimeChart";
import { CategoryBreakdownChart } from "@/components/charts/CategoryBreakdownChart";
import { getCategoryLabel } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function HistoryPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [authLoading, isAuthenticated, router]);

  const { data: history, isLoading: historyLoading } = useUserHistory(
    user?.id ?? null,
  );
  const { data: stats, isLoading: statsLoading } = useUserStats(
    user?.id ?? null,
  );
  const { data: races } = useRaces({ season: 2026 });

  const raceMap = new Map(races?.map((r) => [r.id, r]) ?? []);

  const chartData = (history?.races ?? []).map((r) => ({
    race_weekend_id: r.race_weekend_id,
    points: r.points,
    label: raceMap.get(r.race_weekend_id)?.name?.substring(0, 12) ?? `R${r.race_weekend_id}`,
  }));

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <h1 className="text-3xl font-bold">My History</h1>

      {/* Stats overview */}
      {statsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <div className="text-2xl font-bold text-white">
              {stats.total_score}
            </div>
            <div className="text-xs text-f1-muted mt-1">Total Points</div>
          </Card>
          <Card>
            <div className="text-2xl font-bold text-white">
              {stats.races_participated}
            </div>
            <div className="text-xs text-f1-muted mt-1">Races Predicted</div>
          </Card>
          <Card>
            <div className="text-lg font-bold text-green-400">
              {stats.best_category
                ? getCategoryLabel(stats.best_category)
                : "--"}
            </div>
            <div className="text-xs text-f1-muted mt-1">Best Category</div>
          </Card>
          <Card>
            <div className="text-lg font-bold text-f1-red">
              {stats.worst_category
                ? getCategoryLabel(stats.worst_category)
                : "--"}
            </div>
            <div className="text-xs text-f1-muted mt-1">Needs Work</div>
          </Card>
        </div>
      ) : null}

      {/* Points over time chart */}
      <Card>
        <CardTitle>Points Over Time</CardTitle>
        <p className="text-sm text-f1-muted mb-4">
          Your scoring progression across the season
        </p>
        {historyLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : chartData.length > 0 ? (
          <AccuracyOverTimeChart data={chartData} />
        ) : (
          <div className="h-[300px] flex items-center justify-center text-f1-muted">
            No race data yet. Submit your first prediction to see stats.
          </div>
        )}
      </Card>

      {/* Category breakdown chart */}
      {stats && stats.categories.length > 0 && (
        <Card>
          <CardTitle>Category Breakdown</CardTitle>
          <p className="text-sm text-f1-muted mb-4">
            Average points per prediction category
          </p>
          <CategoryBreakdownChart categories={stats.categories} />
        </Card>
      )}

      {/* Race-by-race breakdown */}
      <Card>
        <CardTitle>Race History</CardTitle>
        {historyLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : history && history.races.length > 0 ? (
          <div className="space-y-2 mt-4">
            {history.races.map((raceScore) => {
              const race = raceMap.get(raceScore.race_weekend_id);
              return (
                <div
                  key={raceScore.race_weekend_id}
                  className="flex items-center justify-between px-4 py-3 rounded-lg bg-f1-surface/50 hover:bg-f1-surface-light transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-f1-muted w-8">
                      R{race?.round ?? "?"}
                    </span>
                    <span className="font-medium text-sm">
                      {race?.name ?? `Race #${raceScore.race_weekend_id}`}
                    </span>
                    <span className="text-xs text-f1-muted">
                      {race?.country}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-white">
                      {raceScore.points} pts
                    </span>
                    <Badge
                      variant={
                        raceScore.points >= 200
                          ? "success"
                          : raceScore.points >= 100
                            ? "warning"
                            : "default"
                      }
                    >
                      {raceScore.points >= 200
                        ? "Great"
                        : raceScore.points >= 100
                          ? "Good"
                          : "OK"}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-f1-muted text-center py-8">
            No race history yet.
          </p>
        )}
      </Card>
    </div>
  );
}
