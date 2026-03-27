"use client";

import type { Team } from "@/types";

interface TeamPickerProps {
  label: string;
  value: number | null;
  onChange: (teamId: number) => void;
  teams: Team[];
  disabled?: boolean;
}

export function TeamPicker({ label, value, onChange, teams, disabled }: TeamPickerProps) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-3">{label}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {teams.map((team) => (
          <button
            key={team.id}
            onClick={() => !disabled && onChange(team.id)}
            disabled={disabled}
            className={`px-3 py-2.5 rounded-lg border text-sm font-medium transition-all duration-200 ${
              value === team.id
                ? "border-f1-red bg-f1-red/10 text-white"
                : "border-f1-border bg-f1-surface/50 text-f1-muted hover:border-gray-500 hover:text-white"
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <span
              className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
              style={{ backgroundColor: team.color_hex }}
            />
            {team.short_name}
          </button>
        ))}
      </div>
    </div>
  );
}
