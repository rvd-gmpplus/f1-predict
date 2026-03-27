"use client";

interface SafetyCarPickerProps {
  willOccur: boolean | null;
  count: number;
  onWillOccurChange: (val: boolean) => void;
  onCountChange: (count: number) => void;
  disabled?: boolean;
}

export function SafetyCarPicker({
  willOccur,
  count,
  onWillOccurChange,
  onCountChange,
  disabled,
}: SafetyCarPickerProps) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-3">Safety Car</h3>
      <div className="flex gap-3 mb-3">
        {[
          { label: "Yes", value: true },
          { label: "No", value: false },
        ].map(({ label, value }) => (
          <button
            key={label}
            onClick={() => !disabled && onWillOccurChange(value)}
            disabled={disabled}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-all ${
              willOccur === value
                ? "bg-f1-red/10 border-f1-red/50 text-white"
                : "border-f1-border text-f1-muted hover:text-white"
            } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {label}
          </button>
        ))}
      </div>
      {willOccur && (
        <div>
          <label className="text-xs text-f1-muted mb-1.5 block">
            How many safety car periods?
          </label>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                onClick={() => !disabled && onCountChange(n)}
                disabled={disabled}
                className={`w-10 h-10 rounded-lg text-sm font-mono font-bold transition-all border ${
                  count === n
                    ? "bg-f1-red/10 border-f1-red/50 text-white"
                    : "border-f1-border text-f1-muted hover:text-white"
                } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
