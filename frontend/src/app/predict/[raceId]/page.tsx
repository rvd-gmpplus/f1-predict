"use client";

import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { PredictionFormWrapper } from "@/components/predict/PredictionFormWrapper";
import { useEffect } from "react";

export default function PredictPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const raceId = Number(params.raceId);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) return null;
  if (isNaN(raceId)) return <div className="p-8">Invalid race ID</div>;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PredictionFormWrapper raceId={raceId} />
    </div>
  );
}
