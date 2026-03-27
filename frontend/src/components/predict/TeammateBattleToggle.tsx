"use client";

import type { Driver, Team } from "@/types";
import { useMemo } from "react";

interface TeammateBattleToggleProps {
  drivers: Driver[];
  teams: Team[];
  /** Map of team_id -> chosen driver_id */
  selections: Record<number, number>;
  onChange: (teamId: number, driverId: number) => void;
  disabled?: boolean;
}

export function TeammateBattleToggle({
  drivers,
  teams,
  selections,
  onChange,
  disabled,
}: TeammateBattleToggleProps) {
  const teamPairs = useMemo(() => {
    const pairs: Array<{ team: Team; drivers: [Driver, Driver] }> = [];
    for (const team of teams) {
      const teamDrivers = drivers.filter((d) => d.team_id === team.id);
      if (teamDrivers.length >= 2) {
        pairs.push({
          team,
          drivers: [teamDrivers[0], teamDrivers[1]],
        });
      }
    }
    return pairs;
  }, [drivers, teams]);

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-3">Teammate Battles</h3>
      <p className="text-xs text-f1-muted mb-4">
        Pick which driver will finish ahead of their teammate
      </p>
      <div className="space-y-2">
        {teamPairs.map(({ team, drivers: [d1, d2] }) => {
          const selected = selections[team.id];
          return (
            <div
              key={team.id}
              className="flex items-center gap-2 p-2 rounded-lg bg-f1-surface/50"
            >
              <span
                className="w-1 h-8 rounded-full flex-shrink-0"
                style={{ backgroundColor: team.color_hex }}
              />
              <button
                onClick={() => !disabled && onChange(team.id, d1.id)}
                disabled={disabled}
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                  selected === d1.id
                    ? "bg-f1-red/20 text-white border border-f1-red/50"
                    : "text-f1-muted hover:text-white hover:bg-white/5 border border-transparent"
                } ${disabled ? "cursor-not-allowed" : ""}`}
              >
                {d1.code}
              </button>
              <span className="text-xs text-f1-muted">vs</span>
              <button
                onClick={() => !disabled && onChange(team.id, d2.id)}
                disabled={disabled}
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                  selected === d2.id
                    ? "bg-f1-red/20 text-white border border-f1-red/50"
                    : "text-f1-muted hover:text-white hover:bg-white/5 border border-transparent"
                } ${disabled ? "cursor-not-allowed" : ""}`}
              >
                {d2.code}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
