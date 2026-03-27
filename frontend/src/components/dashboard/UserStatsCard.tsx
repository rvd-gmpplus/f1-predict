import { Card } from "@/components/ui/Card";
import type { User } from "@/types";

interface UserStatsCardProps {
  user: User;
  seasonRank?: number;
  hasPrediction: boolean;
}

export function UserStatsCard({ user, seasonRank, hasPrediction }: UserStatsCardProps) {
  return (
    <Card>
      <h3 className="text-sm font-medium text-f1-muted mb-4">Your Stats</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-2xl font-bold text-white">{user.total_score}</div>
          <div className="text-xs text-f1-muted">Total Points</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            {seasonRank ? `#${seasonRank}` : "--"}
          </div>
          <div className="text-xs text-f1-muted">Season Rank</div>
        </div>
        <div className="col-span-2">
          <div className="flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                hasPrediction ? "bg-green-400" : "bg-yellow-400 animate-pulse"
              }`}
            />
            <span className="text-sm text-gray-300">
              {hasPrediction
                ? "Prediction submitted"
                : "No prediction yet"}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}
