"use client";

import { useAuth } from "@/hooks/useAuth";
import { useActiveRace, useRace, useDrivers, useTeams } from "@/hooks/useRaces";
import { useMyPrediction } from "@/hooks/usePredictions";
import { useSeasonLeaderboard } from "@/hooks/useLeaderboard";
import { RaceHeader } from "@/components/dashboard/RaceHeader";
import { CountdownTimer } from "@/components/dashboard/CountdownTimer";
import { UserStatsCard } from "@/components/dashboard/UserStatsCard";
import { AIPredictionsPanel } from "@/components/dashboard/AIPredictionsPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [authLoading, isAuthenticated, router]);

  const { data: activeRace, isLoading: raceLoading } = useActiveRace();
  const raceId = activeRace?.id ?? null;
  const { data: raceDetail } = useRace(raceId);
  const { data: prediction } = useMyPrediction(raceId);
  const { data: leaderboard } = useSeasonLeaderboard();
  const { data: drivers } = useDrivers();
  const { data: teams } = useTeams();

  const userRank = leaderboard?.find((e) => e.user_id === user?.id)?.rank;

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <Skeleton className="h-48 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Race header */}
      {raceLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : activeRace ? (
        <RaceHeader race={activeRace} />
      ) : (
        <div className="card-glass p-8 text-center">
          <h2 className="text-xl font-semibold mb-2">No Active Race</h2>
          <p className="text-f1-muted">
            Check the{" "}
            <Link href="/calendar" className="text-f1-red hover:underline">
              calendar
            </Link>{" "}
            for upcoming races.
          </p>
        </div>
      )}

      {/* Grid: Countdown, Stats, Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <CountdownTimer deadline={activeRace?.prediction_deadline ?? null} />

        {user && (
          <UserStatsCard
            user={user}
            seasonRank={userRank}
            hasPrediction={!!prediction}
          />
        )}

        {/* Quick actions */}
        <div className="card-glass p-6 flex flex-col gap-3">
          <h3 className="text-sm font-medium text-f1-muted mb-2">Quick Actions</h3>
          {raceId && (
            <Link href={`/predict/${raceId}`}>
              <Button variant="primary" className="w-full">
                {prediction ? "View Prediction" : "Make Prediction"}
              </Button>
            </Link>
          )}
          <Link href="/leaderboard">
            <Button variant="secondary" className="w-full">
              View Leaderboard
            </Button>
          </Link>
          <Link href="/ai-insights">
            <Button variant="ghost" className="w-full text-left">
              AI Insights
            </Button>
          </Link>
        </div>
      </div>

      {/* AI Predictions Panel */}
      {raceDetail && drivers && teams && (
        <AIPredictionsPanel
          predictions={raceDetail.ai_predictions}
          drivers={drivers}
          teams={teams}
        />
      )}
    </div>
  );
}
