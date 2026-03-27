"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface AccuracyOverTimeChartProps {
  data: Array<{ race_weekend_id: number; points: number; label?: string }>;
}

export function AccuracyOverTimeChart({ data }: AccuracyOverTimeChartProps) {
  const chartData = data.map((d, i) => ({
    race: d.label ?? `R${i + 1}`,
    points: d.points,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="colorPoints" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#E10600" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#E10600" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A4A" />
        <XAxis dataKey="race" stroke="#4A4A6A" fontSize={12} />
        <YAxis stroke="#4A4A6A" fontSize={12} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1A1A2E",
            border: "1px solid #2A2A4A",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Area
          type="monotone"
          dataKey="points"
          stroke="#E10600"
          strokeWidth={2}
          fill="url(#colorPoints)"
          dot={{ r: 4, fill: "#E10600" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
