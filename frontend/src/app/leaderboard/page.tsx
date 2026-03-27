"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useSeasonLeaderboard, useRaceLeaderboard } from "@/hooks/useLeaderboard";
import { useRaces } from "@/hooks/useRaces";
import { LeaderboardTable } from "@/components/leaderboard/LeaderboardTable";
import { Tabs } from "@/components/ui/Tabs";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Select } from "@/components/ui/Select";

const tabs = [
  { id: "season", label: "Season" },
  { id: "race", label: "Last Race" },
  { id: "vs-ai", label: "vs AI" },
];

export default function LeaderboardPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("season");
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(null);

  const { data: seasonData, isLoading: seasonLoading } = useSeasonLeaderboard();
  const { data: completedRaces } = useRaces({ status: "completed" });

  // Default to most recent completed race
  const raceIdForTab = selectedRaceId ?? completedRaces?.[completedRaces.length - 1]?.id ?? null;
  const { data: raceData, isLoading: raceLoading } = useRaceLeaderboard(
    activeTab === "race" ? raceIdForTab : null,
  );

  // For vs AI tab, filter season leaderboard
  const aiEntry = seasonData?.find((e) => e.is_ai);
  const vsAiData = seasonData?.map((entry) => ({
    ...entry,
    // Simple head-to-head: compare total scores vs AI
  }));

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <h1 className="text-3xl font-bold">Leaderboard</h1>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === "season" && (
        <Card className="p-0 overflow-hidden">
          {seasonLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <LeaderboardTable
              entries={seasonData ?? []}
              currentUserId={user?.id}
            />
          )}
        </Card>
      )}

      {activeTab === "race" && (
        <>
          {completedRaces && completedRaces.length > 0 && (
            <Select
              label="Select Race"
              value={raceIdForTab ?? ""}
              onChange={(e) => setSelectedRaceId(Number(e.target.value))}
            >
              {completedRaces.map((race) => (
                <option key={race.id} value={race.id}>
                  Round {race.round} &mdash; {race.name}
                </option>
              ))}
            </Select>
          )}
          <Card className="p-0 overflow-hidden">
            {raceLoading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 10 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : (
              <LeaderboardTable
                entries={raceData ?? []}
                currentUserId={user?.id}
                showBestWeekend={false}
              />
            )}
          </Card>
        </>
      )}

      {activeTab === "vs-ai" && (
        <Card>
          {aiEntry ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 rounded-xl bg-f1-surface/80 border border-f1-blue/30">
                <div>
                  <h3 className="font-semibold text-f1-blue">AI Model</h3>
                  <p className="text-sm text-f1-muted">Season Score</p>
                </div>
                <span className="text-2xl font-mono font-bold text-f1-blue">
                  {aiEntry.total_score}
                </span>
              </div>

              {user && (
                <div className="flex items-center justify-between p-4 rounded-xl bg-f1-surface/80 border border-f1-red/30">
                  <div>
                    <h3 className="font-semibold text-f1-red">You ({user.username})</h3>
                    <p className="text-sm text-f1-muted">Season Score</p>
                  </div>
                  <span className="text-2xl font-mono font-bold text-f1-red">
                    {user.total_score}
                  </span>
                </div>
              )}

              <LeaderboardTable
                entries={vsAiData ?? []}
                currentUserId={user?.id}
              />
            </div>
          ) : (
            <p className="text-f1-muted text-center py-8">
              AI model has not participated in any races yet.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
