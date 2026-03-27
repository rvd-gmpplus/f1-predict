"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import type { Driver, Team } from "@/types";

interface DriverPickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (driverId: number) => void;
  drivers: Driver[];
  teams: Team[];
  excludeIds?: number[];
  title?: string;
}

export function DriverPicker({
  open,
  onClose,
  onSelect,
  drivers,
  teams,
  excludeIds = [],
  title = "Select Driver",
}: DriverPickerProps) {
  const [search, setSearch] = useState("");
  const teamMap = new Map(teams.map((t) => [t.id, t]));

  const filtered = drivers
    .filter((d) => !excludeIds.includes(d.id))
    .filter(
      (d) =>
        d.full_name.toLowerCase().includes(search.toLowerCase()) ||
        d.code.toLowerCase().includes(search.toLowerCase()),
    );

  // Group by team
  const byTeam = filtered.reduce(
    (acc, d) => {
      const teamName = teamMap.get(d.team_id)?.name ?? "Unknown";
      if (!acc[teamName]) acc[teamName] = [];
      acc[teamName].push(d);
      return acc;
    },
    {} as Record<string, Driver[]>,
  );

  return (
    <Dialog open={open} onClose={onClose} className="max-h-[80vh] overflow-y-auto">
      <h2 className="text-lg font-bold mb-4">{title}</h2>

      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search drivers..."
        className="input-field mb-4"
        autoFocus
      />

      <div className="space-y-4">
        {Object.entries(byTeam).map(([teamName, teamDrivers]) => {
          const team = teams.find((t) => t.name === teamName);
          return (
            <div key={teamName}>
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-1.5 h-4 rounded-full"
                  style={{ backgroundColor: team?.color_hex ?? "#666" }}
                />
                <span className="text-xs font-medium text-f1-muted uppercase tracking-wider">
                  {teamName}
                </span>
              </div>
              {teamDrivers.map((driver) => (
                <button
                  key={driver.id}
                  onClick={() => {
                    onSelect(driver.id);
                    onClose();
                    setSearch("");
                  }}
                  className="w-full text-left px-4 py-2.5 rounded-lg hover:bg-f1-surface-light transition-colors flex items-center gap-3"
                >
                  <span className="font-mono text-sm font-bold text-f1-red w-8">
                    {driver.number}
                  </span>
                  <span className="font-medium">{driver.code}</span>
                  <span className="text-f1-muted text-sm">{driver.full_name}</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </Dialog>
  );
}
