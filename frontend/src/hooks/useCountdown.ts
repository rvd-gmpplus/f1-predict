"use client";

import { useState, useEffect } from "react";
import { formatCountdown } from "@/lib/utils";

export function useCountdown(targetDate: string | null) {
  const [countdown, setCountdown] = useState(() => {
    if (!targetDate) return { days: 0, hours: 0, minutes: 0, seconds: 0, expired: true };
    return formatCountdown(new Date(targetDate));
  });

  useEffect(() => {
    if (!targetDate) return;

    const target = new Date(targetDate);

    const tick = () => {
      setCountdown(formatCountdown(target));
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [targetDate]);

  return countdown;
}
