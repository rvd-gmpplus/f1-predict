"use client";

import type { Driver, Team } from "@/types";
import { useState } from "react";
import { DriverPicker } from "./DriverPicker";

interface DNFPickerProps {
  selectedDriverIds: number[];
  onChange: (driverIds: number[]) => void;
  drivers: Driver[];
  teams: Team[];
  disabled?: boolean;
}

export function DNFPicker({
  selectedDriverIds,
  onChange,
  drivers,
  teams,
  disabled,
}: DNFPickerProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const teamMap = new Map(teams.map((t) => [t.id, t]));

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-1">DNF Predictions</h3>
      <p className="text-xs text-f1-muted mb-3">Pick 0-3 drivers to retire</p>

      <div className="space-y-2 mb-2">
        {selectedDriverIds.map((id) => {
          const driver = drivers.find((d) => d.id === id);
          const team = driver ? teamMap.get(driver.team_id) : null;
          return (
            <div
              key={id}
              className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-f1-surface/80 border border-f1-border"
            >
              <div className="flex items-center gap-3">
                <span
                  className="w-1 h-4 rounded-full"
                  style={{ backgroundColor: team?.color_hex ?? "#666" }}
                />
                <span className="font-medium text-sm">
                  {driver?.code}{" "}
                  <span className="text-f1-muted">{driver?.full_name}</span>
                </span>
              </div>
              {!disabled && (
                <button
                  onClick={() => onChange(selectedDriverIds.filter((i) => i !== id))}
                  className="text-f1-muted hover:text-f1-red"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {selectedDriverIds.length < 3 && !disabled && (
        <button
          onClick={() => setPickerOpen(true)}
          className="w-full py-3 border-2 border-dashed border-f1-border rounded-lg text-f1-muted hover:border-f1-red hover:text-f1-red transition-all text-sm"
        >
          + Add DNF driver ({selectedDriverIds.length}/3)
        </button>
      )}

      <DriverPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(id) => {
          if (selectedDriverIds.length < 3) {
            onChange([...selectedDriverIds, id]);
          }
        }}
        drivers={drivers}
        teams={teams}
        excludeIds={selectedDriverIds}
        title="Select DNF Driver"
      />
    </div>
  );
}
