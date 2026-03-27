"use client";

import { useCountdown } from "@/hooks/useCountdown";
import { Card } from "@/components/ui/Card";

interface CountdownTimerProps {
  deadline: string | null;
}

export function CountdownTimer({ deadline }: CountdownTimerProps) {
  const { days, hours, minutes, seconds, expired } = useCountdown(deadline);

  if (!deadline) return null;

  return (
    <Card className={expired ? "border-f1-red/50" : "border-f1-blue/30"}>
      <div className="text-center">
        <h3 className="text-sm font-medium text-f1-muted mb-3">
          {expired ? "Predictions Locked" : "Prediction Deadline"}
        </h3>

        {expired ? (
          <div className="flex items-center justify-center gap-2 text-f1-red">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span className="font-semibold">Deadline Passed</span>
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {[
              { value: days, label: "Days" },
              { value: hours, label: "Hours" },
              { value: minutes, label: "Min" },
              { value: seconds, label: "Sec" },
            ].map(({ value, label }) => (
              <div key={label}>
                <div className="text-2xl sm:text-3xl font-mono font-bold text-white">
                  {String(value).padStart(2, "0")}
                </div>
                <div className="text-xs text-f1-muted mt-1">{label}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
