"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { CategoryStat } from "@/types";
import { getCategoryLabel } from "@/lib/utils";

interface CategoryBreakdownChartProps {
  categories: CategoryStat[];
}

export function CategoryBreakdownChart({
  categories,
}: CategoryBreakdownChartProps) {
  const data = categories.map((c) => ({
    name: getCategoryLabel(c.category),
    avgPoints: c.avg_points,
    totalPoints: c.total_points,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical" margin={{ left: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A4A" horizontal={false} />
        <XAxis type="number" stroke="#4A4A6A" fontSize={12} />
        <YAxis
          type="category"
          dataKey="name"
          stroke="#4A4A6A"
          fontSize={11}
          width={120}
          tick={{ fill: "#9CA3AF" }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1A1A2E",
            border: "1px solid #2A2A4A",
            borderRadius: "8px",
            color: "#fff",
          }}
        />
        <Bar dataKey="avgPoints" radius={[0, 4, 4, 0]} name="Avg Points">
          {data.map((_, i) => (
            <Cell
              key={i}
              fill={i === 0 ? "#E10600" : i < 3 ? "#0090FF" : "#4A4A6A"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
