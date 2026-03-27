import type { RaceWeekend } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/utils";

interface RaceHeaderProps {
  race: RaceWeekend;
}

export function RaceHeader({ race }: RaceHeaderProps) {
  const statusVariant = {
    upcoming: "warning" as const,
    active: "success" as const,
    completed: "default" as const,
  };

  return (
    <div className="relative overflow-hidden rounded-xl">
      {/* Hero background */}
      <div
        className="absolute inset-0 bg-cover bg-center opacity-20"
        style={{ backgroundImage: "url('/images/hero-pitstop.png')" }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-f1-carbon via-f1-carbon/90 to-transparent" />

      <div className="relative p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
          <Badge variant={statusVariant[race.status]}>
            {race.status.charAt(0).toUpperCase() + race.status.slice(1)}
          </Badge>
          <span className="text-sm text-f1-muted">
            Round {race.round} &middot; {race.season} Season
          </span>
          {race.is_sprint_weekend && (
            <Badge variant="info">Sprint Weekend</Badge>
          )}
        </div>

        <h1 className="text-3xl sm:text-4xl font-bold mb-2">{race.name}</h1>
        <p className="text-lg text-gray-400 mb-4">
          {race.country} &middot; {race.circuit_id}
        </p>

        <div className="flex flex-wrap gap-6 text-sm text-gray-400">
          {race.quali_time && (
            <div>
              <span className="text-f1-muted">Qualifying:</span>{" "}
              <span className="text-white">{formatDateTime(race.quali_time)}</span>
            </div>
          )}
          {race.race_time && (
            <div>
              <span className="text-f1-muted">Race:</span>{" "}
              <span className="text-white">{formatDateTime(race.race_time)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
