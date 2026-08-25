"use client";

import { useEffect, useRef, useState } from "react";
import type { PriceTick, WatchlistItem } from "@/lib/types";
import type { PricePoint } from "@/lib/usePriceStream";
import { formatPercent } from "@/lib/format";
import Sparkline from "./Sparkline";

interface WatchlistProps {
  tickers: WatchlistItem[];
  prices: Record<string, PriceTick>;
  history: Record<string, PricePoint[]>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

function useFlash(prices: Record<string, PriceTick>) {
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});
  const lastPrice = useRef<Record<string, number>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    for (const [ticker, tick] of Object.entries(prices)) {
      const prev = lastPrice.current[ticker];
      if (prev !== undefined && prev !== tick.price) {
        setFlash((f) => ({ ...f, [ticker]: tick.price > prev ? "up" : "down" }));
        clearTimeout(timers.current[ticker]);
        timers.current[ticker] = setTimeout(() => {
          setFlash((f) => {
            const next = { ...f };
            delete next[ticker];
            return next;
          });
        }, 500);
      }
      lastPrice.current[ticker] = tick.price;
    }
  }, [prices]);

  return flash;
}

export default function Watchlist({
  tickers,
  prices,
  history,
  selectedTicker,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistProps) {
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const flash = useFlash(prices);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) return;
    setAdding(true);
    try {
      await onAdd(ticker);
      setNewTicker("");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Watchlist
        </h2>
        <form onSubmit={handleAdd} className="flex items-center gap-1">
          <input
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)}
            placeholder="Ticker"
            className="w-16 rounded border border-border bg-background px-2 py-1 text-xs uppercase outline-none focus:border-accent-blue"
          />
          <button
            type="submit"
            disabled={adding || !newTicker.trim()}
            className="rounded bg-accent-blue px-2 py-1 text-xs font-medium text-background disabled:opacity-40"
          >
            Add
          </button>
        </form>
      </div>

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-panel text-[10px] uppercase text-muted">
            <tr>
              <th className="px-3 py-1.5 font-medium">Ticker</th>
              <th className="px-3 py-1.5 font-medium">Price</th>
              <th className="px-3 py-1.5 font-medium">Chg %</th>
              <th className="px-3 py-1.5 font-medium">Chart</th>
              <th className="px-3 py-1.5 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((item) => {
              const tick = prices[item.ticker];
              const price = tick?.price ?? item.price;
              const changePercent = tick?.change_percent ?? item.change_percent;
              const direction = tick?.direction ?? item.direction;
              const flashClass =
                flash[item.ticker] === "up"
                  ? "flash-up"
                  : flash[item.ticker] === "down"
                    ? "flash-down"
                    : "";

              return (
                <tr
                  key={item.ticker}
                  onClick={() => onSelect(item.ticker)}
                  className={`cursor-pointer border-b border-border/60 hover:bg-white/5 ${
                    selectedTicker === item.ticker ? "bg-white/5" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 font-mono font-semibold">{item.ticker}</td>
                  <td className={`px-3 py-1.5 font-mono ${flashClass}`}>
                    {price !== null ? price.toFixed(2) : "—"}
                  </td>
                  <td
                    className={`px-3 py-1.5 font-mono ${
                      direction === "up"
                        ? "text-up"
                        : direction === "down"
                          ? "text-down"
                          : "text-muted"
                    }`}
                  >
                    {changePercent !== null ? formatPercent(changePercent) : "—"}
                  </td>
                  <td className="px-3 py-1.5">
                    <Sparkline
                      data={history[item.ticker] ?? []}
                      positive={direction !== "down"}
                    />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(item.ticker);
                      }}
                      className="text-muted hover:text-down"
                      aria-label={`Remove ${item.ticker}`}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
