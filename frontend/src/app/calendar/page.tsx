"use client";

import { useRaces } from "@/hooks/useRaces";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate, formatDateTime } from "@/lib/utils";
import Link from "next/link";

export default function CalendarPage() {
  const { data: races, isLoading } = useRaces({ season: 2026 });

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <h1 className="text-3xl font-bold">2026 Calendar</h1>
      <p className="text-f1-muted">
        Full season schedule with prediction status
      </p>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {races?.map((race) => {
            const statusConfig = {
              completed: {
                variant: "success" as const,
                label: "Completed",
              },
              active: {
                variant: "danger" as const,
                label: "Live",
              },
              upcoming: {
                variant: "default" as const,
                label: "Upcoming",
              },
            };
            const status = statusConfig[race.status];

            return (
              <Link key={race.id} href={`/predict/${race.id}`}>
                <Card hover className="flex flex-col sm:flex-row sm:items-center gap-4 group">
                  {/* Round number */}
                  <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-f1-surface flex items-center justify-center border border-f1-border">
                    <span className="text-lg font-mono font-bold text-f1-muted group-hover:text-white transition-colors">
                      R{String(race.round).padStart(2, "0")}
                    </span>
                  </div>

                  {/* Race info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold truncate">{race.name}</h3>
                      <Badge variant={status.variant}>{status.label}</Badge>
                      {race.is_sprint_weekend && (
                        <Badge variant="info">Sprint</Badge>
                      )}
                    </div>
                    <p className="text-sm text-f1-muted">{race.country}</p>
                  </div>

                  {/* Dates */}
                  <div className="flex flex-col items-end text-right text-sm flex-shrink-0">
                    {race.race_time && (
                      <span className="text-gray-300">
                        {formatDate(race.race_time)}
                      </span>
                    )}
                    {race.prediction_deadline && (
                      <span className="text-xs text-f1-muted">
                        Deadline: {formatDateTime(race.prediction_deadline)}
                      </span>
                    )}
                  </div>

                  {/* Arrow */}
                  <div className="hidden sm:block flex-shrink-0">
                    <svg
                      className="w-5 h-5 text-f1-muted group-hover:text-f1-red transition-colors"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
