"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { MLPrediction } from "@/types";
import { getStageLabel } from "@/lib/utils";

interface ConfidenceEvolutionChartProps {
  predictions: MLPrediction[];
  category: string;
}

export function ConfidenceEvolutionChart({
  predictions,
  category,
}: ConfidenceEvolutionChartProps) {
  const filtered = predictions.filter((p) => p.category === category);

  // Group by session stage
  const stageOrder = ["pre", "fp1", "fp2", "fp3", "quali"];
  const stages = stageOrder.filter((s) =>
    filtered.some((p) => p.session_stage === s),
  );

  // For position-based categories, track each position across stages
  const positions = [...new Set(filtered.map((p) => p.position).filter(Boolean))].sort(
    (a, b) => (a ?? 0) - (b ?? 0),
  );

  const data = stages.map((stage) => {
    const stagePreds = filtered.filter((p) => p.session_stage === stage);
    const point: Record<string, unknown> = { stage: getStageLabel(stage) };
    if (positions.length > 0) {
      positions.forEach((pos) => {
        const pred = stagePreds.find((p) => p.position === pos);
        point[`P${pos}`] = pred ? Math.round(pred.confidence * 100) : null;
      });
    } else {
      // Single-pick category
      const pred = stagePreds[0];
      point["confidence"] = pred ? Math.round(pred.confidence * 100) : null;
    }
    return point;
  });

  const colors = ["#E10600", "#0090FF", "#00D2BE", "#FF8700", "#9B59B6"];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A4A" />
        <XAxis dataKey="stage" stroke="#4A4A6A" fontSize={12} />
        <YAxis
          domain={[0, 100]}
          stroke="#4A4A6A"
          fontSize={12}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1A1A2E",
            border: "1px solid #2A2A4A",
            borderRadius: "8px",
            color: "#fff",
          }}
          formatter={(value: number) => `${value}%`}
        />
        <Legend />
        {positions.length > 0
          ? positions.map((pos, i) => (
              <Line
                key={pos}
                type="monotone"
                dataKey={`P${pos}`}
                stroke={colors[i % colors.length]}
                strokeWidth={2}
                dot={{ r: 4 }}
                connectNulls
              />
            ))
          : (
              <Line
                type="monotone"
                dataKey="confidence"
                stroke="#E10600"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
            )}
      </LineChart>
    </ResponsiveContainer>
  );
}
