"use client";

import type { Position } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

interface PositionsTableProps {
  positions: Position[];
  selectedTicker?: string | null;
  onSelect?: (ticker: string) => void;
}

export default function PositionsTable({
  positions,
  selectedTicker,
  onSelect,
}: PositionsTableProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Positions
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-panel text-[10px] uppercase text-muted">
            <tr>
              <th className="px-3 py-1.5 font-medium">Ticker</th>
              <th className="px-3 py-1.5 font-medium">Qty</th>
              <th className="px-3 py-1.5 font-medium">Avg Cost</th>
              <th className="px-3 py-1.5 font-medium">Price</th>
              <th className="px-3 py-1.5 font-medium">P&amp;L</th>
              <th className="px-3 py-1.5 font-medium">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-muted">
                  No positions yet
                </td>
              </tr>
            ) : (
              positions.map((p) => (
                <tr
                  key={p.ticker}
                  onClick={() => onSelect?.(p.ticker)}
                  className={`border-b border-border/60 ${
                    onSelect ? "cursor-pointer hover:bg-white/5" : ""
                  } ${selectedTicker === p.ticker ? "bg-white/5" : ""}`}
                >
                  <td className="px-3 py-1.5 font-mono font-semibold">{p.ticker}</td>
                  <td className="px-3 py-1.5 font-mono">{p.quantity}</td>
                  <td className="px-3 py-1.5 font-mono">{p.avg_cost.toFixed(2)}</td>
                  <td className="px-3 py-1.5 font-mono">{p.current_price.toFixed(2)}</td>
                  <td
                    className={`px-3 py-1.5 font-mono ${
                      p.unrealized_pnl >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {formatCurrency(p.unrealized_pnl)}
                  </td>
                  <td
                    className={`px-3 py-1.5 font-mono ${
                      p.unrealized_pnl_percent >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {formatPercent(p.unrealized_pnl_percent)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
