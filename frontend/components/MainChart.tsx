"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "@/lib/usePriceStream";

interface MainChartProps {
  ticker: string | null;
  data: PricePoint[];
}

export default function MainChart({ ticker, data }: MainChartProps) {
  return (
    <div className="flex h-full flex-col border-b border-border">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {ticker ? `${ticker} — Live Price` : "Select a ticker"}
        </h2>
      </div>
      <div className="min-h-0 flex-1 p-2">
        {!ticker || data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            {ticker ? "Accumulating price history…" : "Click a ticker in the watchlist"}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="mainChartFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={(t) => new Date(t * 1000).toLocaleTimeString()}
                stroke="var(--muted)"
                fontSize={10}
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                stroke="var(--muted)"
                fontSize={10}
                tickFormatter={(v) => v.toFixed(2)}
                width={60}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
                labelFormatter={(t) => new Date((t as number) * 1000).toLocaleTimeString()}
                formatter={(value) => Number(value).toFixed(2)}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke="var(--accent-blue)"
                fill="url(#mainChartFill)"
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
