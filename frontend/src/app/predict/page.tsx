"use client";

import { useRouter } from "next/navigation";
import { useActiveRace } from "@/hooks/useRaces";
import { useAuth } from "@/hooks/useAuth";
import { Skeleton } from "@/components/ui/Skeleton";
import { useEffect } from "react";

export default function PredictIndexPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { data: race, isLoading } = useActiveRace();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
      return;
    }
    if (race) {
      router.replace(`/predict/${race.id}`);
    }
  }, [race, authLoading, isAuthenticated, router]);

  if (isLoading || authLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Skeleton className="h-12 w-64 mb-6" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 text-center">
      <p className="text-f1-muted">No active race found. Check the calendar.</p>
    </div>
  );
}
