"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDrivers, useTeams, useRace } from "@/hooks/useRaces";
import { useMyPrediction, useSubmitPrediction } from "@/hooks/usePredictions";
import { useCountdown } from "@/hooks/useCountdown";
import { Top5DragList } from "./Top5DragList";
import { DriverPicker } from "./DriverPicker";
import { TeamPicker } from "./TeamPicker";
import { TeammateBattleToggle } from "./TeammateBattleToggle";
import { SafetyCarPicker } from "./SafetyCarPicker";
import { DNFPicker } from "./DNFPicker";
import { TireStrategyPicker } from "./TireStrategyPicker";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import type { PredictionDetailInput, PredictionCategory } from "@/types";

interface PredictionFormWrapperProps {
  raceId: number;
}

export function PredictionFormWrapper({ raceId }: PredictionFormWrapperProps) {
  const router = useRouter();
  const { data: race, isLoading: raceLoading } = useRace(raceId);
  const { data: drivers = [], isLoading: driversLoading } = useDrivers();
  const { data: teams = [], isLoading: teamsLoading } = useTeams();
  const { data: existingPrediction } = useMyPrediction(raceId);
  const submitMutation = useSubmitPrediction(raceId);
  const { expired } = useCountdown(race?.prediction_deadline ?? null);

  const isLocked = expired || !!existingPrediction;

  // Form state
  const [qualiTop5, setQualiTop5] = useState<number[]>([]);
  const [raceTop5, setRaceTop5] = useState<number[]>([]);
  const [sprintTop5, setSprintTop5] = useState<number[]>([]);
  const [fastestLap, setFastestLap] = useState<number | null>(null);
  const [constructorPoints, setConstructorPoints] = useState<number | null>(null);
  const [quickestPitstop, setQuickestPitstop] = useState<number | null>(null);
  const [teammateBattles, setTeammateBattles] = useState<Record<number, number>>({});
  const [safetyCar, setSafetyCar] = useState<boolean | null>(null);
  const [safetyCarCount, setSafetyCarCount] = useState<number>(1);
  const [dnfDrivers, setDnfDrivers] = useState<number[]>([]);
  const [tireStrategy, setTireStrategy] = useState<number | null>(null);

  // Driver picker state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<
    "quali" | "race" | "sprint" | "fastestLap" | null
  >(null);

  // Confirmation dialog
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const handleDriverPickerOpen = useCallback(
    (target: "quali" | "race" | "sprint" | "fastestLap") => {
      setPickerTarget(target);
      setPickerOpen(true);
    },
    [],
  );

  const getExcludeIds = () => {
    if (pickerTarget === "quali") return qualiTop5;
    if (pickerTarget === "race") return raceTop5;
    if (pickerTarget === "sprint") return sprintTop5;
    return [];
  };

  const handleDriverSelected = (driverId: number) => {
    if (pickerTarget === "quali" && qualiTop5.length < 5) {
      setQualiTop5([...qualiTop5, driverId]);
    } else if (pickerTarget === "race" && raceTop5.length < 5) {
      setRaceTop5([...raceTop5, driverId]);
    } else if (pickerTarget === "sprint" && sprintTop5.length < 5) {
      setSprintTop5([...sprintTop5, driverId]);
    } else if (pickerTarget === "fastestLap") {
      setFastestLap(driverId);
    }
  };

  const buildSubmission = (): PredictionDetailInput[] => {
    const details: PredictionDetailInput[] = [];

    qualiTop5.forEach((driverId, i) => {
      details.push({
        category: "qualifying_top5" as PredictionCategory,
        position: i + 1,
        driver_id: driverId,
      });
    });

    raceTop5.forEach((driverId, i) => {
      details.push({
        category: "race_top5" as PredictionCategory,
        position: i + 1,
        driver_id: driverId,
      });
    });

    if (race?.is_sprint_weekend) {
      sprintTop5.forEach((driverId, i) => {
        details.push({
          category: "sprint_top5" as PredictionCategory,
          position: i + 1,
          driver_id: driverId,
        });
      });
    }

    if (fastestLap) {
      details.push({
        category: "fastest_lap" as PredictionCategory,
        driver_id: fastestLap,
      });
    }

    if (constructorPoints) {
      details.push({
        category: "constructor_points" as PredictionCategory,
        team_id: constructorPoints,
      });
    }

    if (quickestPitstop) {
      details.push({
        category: "quickest_pitstop" as PredictionCategory,
        team_id: quickestPitstop,
      });
    }

    Object.entries(teammateBattles).forEach(([teamId, driverId]) => {
      details.push({
        category: "teammate_battle" as PredictionCategory,
        team_id: Number(teamId),
        driver_id: driverId,
      });
    });

    if (safetyCar !== null) {
      details.push({
        category: "safety_car" as PredictionCategory,
        value: safetyCar
          ? `yes:${safetyCarCount}`
          : "no",
      });
    }

    dnfDrivers.forEach((driverId) => {
      details.push({
        category: "dnf" as PredictionCategory,
        driver_id: driverId,
      });
    });

    if (tireStrategy !== null) {
      details.push({
        category: "tire_strategy" as PredictionCategory,
        value: String(tireStrategy),
      });
    }

    return details;
  };

  const handleSubmit = async () => {
    setSubmitError("");
    try {
      await submitMutation.mutateAsync({ details: buildSubmission() });
      setConfirmOpen(false);
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to submit prediction";
      setSubmitError(message);
    }
  };

  if (raceLoading || driversLoading || teamsLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{race?.name}</h1>
          <p className="text-f1-muted">
            Round {race?.round} &middot; {race?.country}
          </p>
        </div>
        {isLocked && (
          <Badge variant="danger">Predictions Locked</Badge>
        )}
      </div>

      {existingPrediction && (
        <div className="bg-green-900/20 border border-green-800 rounded-xl p-4 flex items-center gap-3">
          <svg className="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-green-300 text-sm">
            Your prediction was submitted on{" "}
            {new Date(existingPrediction.submitted_at).toLocaleString()}.
          </span>
        </div>
      )}

      {/* Position-based categories */}
      <Card>
        <Top5DragList
          label="Qualifying Top 5"
          selectedDriverIds={qualiTop5}
          onOrderChange={setQualiTop5}
          drivers={drivers}
          teams={teams}
          onAddDriver={() => handleDriverPickerOpen("quali")}
          onRemoveDriver={(id) => setQualiTop5(qualiTop5.filter((d) => d !== id))}
          disabled={isLocked}
        />
      </Card>

      <Card>
        <Top5DragList
          label="Race Top 5"
          selectedDriverIds={raceTop5}
          onOrderChange={setRaceTop5}
          drivers={drivers}
          teams={teams}
          onAddDriver={() => handleDriverPickerOpen("race")}
          onRemoveDriver={(id) => setRaceTop5(raceTop5.filter((d) => d !== id))}
          disabled={isLocked}
        />
      </Card>

      {race?.is_sprint_weekend && (
        <Card>
          <Top5DragList
            label="Sprint Top 5"
            selectedDriverIds={sprintTop5}
            onOrderChange={setSprintTop5}
            drivers={drivers}
            teams={teams}
            onAddDriver={() => handleDriverPickerOpen("sprint")}
            onRemoveDriver={(id) =>
              setSprintTop5(sprintTop5.filter((d) => d !== id))
            }
            disabled={isLocked}
          />
        </Card>
      )}

      {/* Single picks */}
      <Card>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Fastest Lap</h3>
        {fastestLap ? (
          <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-f1-surface/80 border border-f1-border">
            <span className="text-sm font-medium">
              {drivers.find((d) => d.id === fastestLap)?.code}{" "}
              <span className="text-f1-muted">
                {drivers.find((d) => d.id === fastestLap)?.full_name}
              </span>
            </span>
            {!isLocked && (
              <button
                onClick={() => setFastestLap(null)}
                className="text-f1-muted hover:text-f1-red"
              >
                Change
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={() => handleDriverPickerOpen("fastestLap")}
            disabled={isLocked}
            className="w-full py-3 border-2 border-dashed border-f1-border rounded-lg text-f1-muted hover:border-f1-red hover:text-f1-red transition-all text-sm disabled:opacity-50"
          >
            + Select driver
          </button>
        )}
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <TeamPicker
            label="Constructor Points (Most Points)"
            value={constructorPoints}
            onChange={setConstructorPoints}
            teams={teams}
            disabled={isLocked}
          />
        </Card>

        <Card>
          <TeamPicker
            label="Quickest Pit Stop"
            value={quickestPitstop}
            onChange={setQuickestPitstop}
            teams={teams}
            disabled={isLocked}
          />
        </Card>
      </div>

      {/* Special categories */}
      <Card>
        <TeammateBattleToggle
          drivers={drivers}
          teams={teams}
          selections={teammateBattles}
          onChange={(teamId, driverId) =>
            setTeammateBattles({ ...teammateBattles, [teamId]: driverId })
          }
          disabled={isLocked}
        />
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <SafetyCarPicker
            willOccur={safetyCar}
            count={safetyCarCount}
            onWillOccurChange={setSafetyCar}
            onCountChange={setSafetyCarCount}
            disabled={isLocked}
          />
        </Card>

        <Card>
          <DNFPicker
            selectedDriverIds={dnfDrivers}
            onChange={setDnfDrivers}
            drivers={drivers}
            teams={teams}
            disabled={isLocked}
          />
        </Card>

        <Card>
          <TireStrategyPicker
            value={tireStrategy}
            onChange={setTireStrategy}
            disabled={isLocked}
          />
        </Card>
      </div>

      {/* Submit */}
      {!isLocked && (
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => router.push("/dashboard")}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => setConfirmOpen(true)}>
            Submit Prediction
          </Button>
        </div>
      )}

      {/* Confirmation dialog */}
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <h2 className="text-lg font-bold mb-2">Confirm Prediction</h2>
        <p className="text-f1-muted text-sm mb-4">
          Once submitted, your prediction will be locked. You can update it
          until the deadline passes.
        </p>
        {submitError && (
          <div className="bg-f1-red/10 border border-f1-red/30 text-f1-red rounded-lg px-4 py-3 text-sm mb-4">
            {submitError}
          </div>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
            Go Back
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={submitMutation.isPending}
          >
            {submitMutation.isPending ? "Submitting..." : "Confirm & Lock"}
          </Button>
        </div>
      </Dialog>

      {/* Driver picker (shared) */}
      <DriverPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={handleDriverSelected}
        drivers={drivers}
        teams={teams}
        excludeIds={getExcludeIds()}
        title={
          pickerTarget === "fastestLap"
            ? "Select Fastest Lap Driver"
            : `Add to ${
                pickerTarget === "quali"
                  ? "Qualifying"
                  : pickerTarget === "sprint"
                    ? "Sprint"
                    : "Race"
              } Top 5`
        }
      />
    </div>
  );
}
