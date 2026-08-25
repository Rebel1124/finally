"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";

interface TradeBarProps {
  defaultTicker: string | null;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<void>;
}

export default function TradeBar({ defaultTicker, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [quantity, setQuantity] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncedTicker, setSyncedTicker] = useState(defaultTicker);

  if (defaultTicker !== syncedTicker) {
    setSyncedTicker(defaultTicker);
    if (defaultTicker) setTicker(defaultTicker);
  }

  async function submit(side: "buy" | "sell") {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) {
      setError("Enter a ticker");
      return;
    }
    const qty = Number(quantity);
    if (!quantity || !qty || qty <= 0) {
      setError("Enter a quantity");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onTrade(symbol, qty, side);
      setQuantity("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Trade failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center gap-2 border-t border-border bg-panel px-3 py-2">
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Ticker"
        className="w-24 rounded border border-border bg-background px-2 py-1.5 text-sm uppercase outline-none focus:border-accent-blue"
      />
      <input
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        type="number"
        min="0"
        step="any"
        placeholder="Qty"
        className="w-24 rounded border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-accent-blue"
      />
      <button
        onClick={() => submit("buy")}
        disabled={submitting}
        className="rounded bg-accent-purple px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
      >
        Buy
      </button>
      <button
        onClick={() => submit("sell")}
        disabled={submitting}
        className="rounded border border-down px-4 py-1.5 text-sm font-medium text-down disabled:opacity-40"
      >
        Sell
      </button>
      {error && <span className="text-xs text-down">{error}</span>}
    </div>
  );
}
