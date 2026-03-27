import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...options,
  });
}

export function formatDateTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCountdown(targetDate: Date): {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  expired: boolean;
} {
  const now = new Date();
  const diff = targetDate.getTime() - now.getTime();

  if (diff <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, expired: true };
  }

  return {
    days: Math.floor(diff / (1000 * 60 * 60 * 24)),
    hours: Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)),
    minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
    seconds: Math.floor((diff % (1000 * 60)) / 1000),
    expired: false,
  };
}

export function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    qualifying_top5: "Qualifying Top 5",
    race_top5: "Race Top 5",
    sprint_top5: "Sprint Top 5",
    fastest_lap: "Fastest Lap",
    constructor_points: "Constructor Points",
    quickest_pitstop: "Quickest Pit Stop",
    teammate_battle: "Teammate Battle",
    safety_car: "Safety Car",
    dnf: "DNFs",
    tire_strategy: "Tire Strategy",
  };
  return labels[category] ?? category;
}

export function getStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    pre: "Pre-Weekend",
    fp1: "After FP1",
    fp2: "After FP2",
    fp3: "After FP3",
    quali: "After Qualifying",
  };
  return labels[stage] ?? stage;
}
