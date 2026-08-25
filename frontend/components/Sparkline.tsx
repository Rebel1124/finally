"use client";

import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import type { PricePoint } from "@/lib/usePriceStream";

interface SparklineProps {
  data: PricePoint[];
  positive: boolean;
}

export default function Sparkline({ data, positive }: SparklineProps) {
  if (data.length < 2) {
    return <div className="h-8 w-24 text-[10px] text-muted flex items-center">accumulating…</div>;
  }

  const color = positive ? "var(--up)" : "var(--down)";

  return (
    <div className="h-8 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <YAxis domain={["dataMin", "dataMax"]} hide />
          <Line
            type="monotone"
            dataKey="price"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
