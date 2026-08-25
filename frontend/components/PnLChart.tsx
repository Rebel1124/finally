"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PortfolioSnapshot } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

interface PnLChartProps {
  snapshots: PortfolioSnapshot[];
}

export default function PnLChart({ snapshots }: PnLChartProps) {
  const data = snapshots.map((s) => ({
    time: new Date(s.recorded_at).getTime(),
    value: s.total_value,
  }));

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Portfolio Value
        </h2>
      </div>
      <div className="min-h-0 flex-1 p-2">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            Not enough history yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={(t) => new Date(t).toLocaleTimeString()}
                stroke="var(--muted)"
                fontSize={10}
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                stroke="var(--muted)"
                fontSize={10}
                tickFormatter={(v) => formatCurrency(v)}
                width={70}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
                labelFormatter={(t) => new Date(t as number).toLocaleTimeString()}
                formatter={(value) => formatCurrency(Number(value))}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--accent-yellow)"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
