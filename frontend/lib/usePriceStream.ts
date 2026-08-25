"use client";

import { useEffect, useRef, useState } from "react";
import type { PriceTick } from "./types";

export type ConnectionStatus = "connecting" | "open" | "reconnecting";

export interface PricePoint {
  time: number;
  price: number;
}

const MAX_HISTORY_POINTS = 500;

export function usePriceStream() {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const historyRef = useRef<Record<string, PricePoint[]>>({});

  useEffect(() => {
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setStatus("open");

    source.onmessage = (event) => {
      setStatus("open");
      const data: Record<string, PriceTick> = JSON.parse(event.data);

      setPrices((prev) => ({ ...prev, ...data }));

      const nextHistory = { ...historyRef.current };
      for (const [ticker, tick] of Object.entries(data)) {
        const points = nextHistory[ticker] ?? [];
        const updated = [...points, { time: tick.timestamp, price: tick.price }];
        nextHistory[ticker] =
          updated.length > MAX_HISTORY_POINTS ? updated.slice(-MAX_HISTORY_POINTS) : updated;
      }
      historyRef.current = nextHistory;
      setHistory(nextHistory);
    };

    source.onerror = () => {
      setStatus(source.readyState === EventSource.CONNECTING ? "reconnecting" : "connecting");
    };

    return () => source.close();
  }, []);

  return { prices, history, status };
}
