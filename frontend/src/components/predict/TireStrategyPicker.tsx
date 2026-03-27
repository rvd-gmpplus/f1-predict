"use client";

interface TireStrategyPickerProps {
  value: number | null;
  onChange: (stops: number) => void;
  disabled?: boolean;
}

export function TireStrategyPicker({ value, onChange, disabled }: TireStrategyPickerProps) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-1">
        Tire Strategy (Winner&apos;s Pit Stops)
      </h3>
      <p className="text-xs text-f1-muted mb-3">
        How many pit stops will the race winner make?
      </p>
      <div className="flex gap-2">
        {[0, 1, 2, 3, 4].map((n) => (
          <button
            key={n}
            onClick={() => !disabled && onChange(n)}
            disabled={disabled}
            className={`flex-1 py-3 rounded-lg text-sm font-mono font-bold transition-all border ${
              value === n
                ? "bg-f1-red/10 border-f1-red/50 text-white"
                : "border-f1-border text-f1-muted hover:text-white"
            } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}
