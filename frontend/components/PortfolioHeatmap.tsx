"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import type { Position } from "@/lib/types";
import { formatPercent } from "@/lib/format";

interface PortfolioHeatmapProps {
  positions: Position[];
}

function colorFor(pnlPercent: number): string {
  const magnitude = Math.min(Math.abs(pnlPercent) / 15, 1);
  const lightness = 22 - magnitude * 10;
  return pnlPercent >= 0
    ? `hsl(142, 55%, ${lightness}%)`
    : `hsl(4, 65%, ${lightness}%)`;
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  ticker?: string;
  unrealized_pnl_percent?: number;
}

function HeatmapCell({ x = 0, y = 0, width = 0, height = 0, ticker, unrealized_pnl_percent = 0 }: CellProps) {
  if (width < 2 || height < 2) return null;
  const showLabel = width > 50 && height > 30;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill: colorFor(unrealized_pnl_percent), stroke: "var(--background)", strokeWidth: 2 }}
      />
      {showLabel && (
        <text x={x + 8} y={y + 20} fill="#ffffff" fontSize={13} fontWeight={600}>
          {ticker}
        </text>
      )}
      {showLabel && (
        <text x={x + 8} y={y + 38} fill="#ffffff" fontSize={11} opacity={0.85}>
          {formatPercent(unrealized_pnl_percent)}
        </text>
      )}
    </g>
  );
}

export default function PortfolioHeatmap({ positions }: PortfolioHeatmapProps) {
  const data = positions.map((p) => ({
    name: p.ticker,
    ticker: p.ticker,
    size: Math.max(p.market_value, 0.01),
    unrealized_pnl_percent: p.unrealized_pnl_percent,
  }));

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Portfolio Heatmap
        </h2>
      </div>
      <div className="min-h-0 flex-1 p-2">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            No positions yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              stroke="var(--background)"
              isAnimationActive={false}
              content={<HeatmapCell />}
            />
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
