"use client";

import type { LeaderboardEntry } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  currentUserId?: number;
  showBestWeekend?: boolean;
}

export function LeaderboardTable({
  entries,
  currentUserId,
  showBestWeekend = true,
}: LeaderboardTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-xs text-f1-muted uppercase tracking-wider border-b border-f1-border">
            <th className="px-4 py-3 w-16">Rank</th>
            <th className="px-4 py-3">Driver</th>
            <th className="px-4 py-3 text-right">Points</th>
            <th className="px-4 py-3 text-right hidden sm:table-cell">Races</th>
            {showBestWeekend && (
              <th className="px-4 py-3 text-right hidden md:table-cell">Best Weekend</th>
            )}
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isCurrentUser = entry.user_id === currentUserId;
            const isTopThree = entry.rank <= 3;

            return (
              <tr
                key={entry.user_id}
                className={cn(
                  "border-b border-f1-border/50 transition-colors",
                  isCurrentUser
                    ? "bg-f1-red/5 border-l-2 border-l-f1-red"
                    : "hover:bg-white/[0.02]",
                )}
              >
                <td className="px-4 py-3.5">
                  <span
                    className={cn(
                      "font-mono font-bold text-sm",
                      entry.rank === 1 && "text-yellow-400",
                      entry.rank === 2 && "text-gray-300",
                      entry.rank === 3 && "text-amber-600",
                      !isTopThree && "text-f1-muted",
                    )}
                  >
                    {entry.rank}
                  </span>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <span className={cn("font-medium", isCurrentUser && "text-f1-red")}>
                      {entry.username}
                    </span>
                    {entry.is_ai && (
                      <Badge variant="info">AI</Badge>
                    )}
                    {isCurrentUser && (
                      <Badge variant="danger">You</Badge>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right">
                  <span className="font-mono font-bold">
                    {entry.total_score}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-right hidden sm:table-cell text-f1-muted">
                  {entry.races_participated}
                </td>
                {showBestWeekend && (
                  <td className="px-4 py-3.5 text-right hidden md:table-cell text-f1-muted font-mono">
                    {entry.best_weekend}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {entries.length === 0 && (
        <div className="text-center py-12 text-f1-muted">
          No data available yet.
        </div>
      )}
    </div>
  );
}
