import type {
  ChatTradeResult,
  ChatWatchlistChangeResult,
  Portfolio,
  PortfolioSnapshot,
  Trade,
  WatchlistItem,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) message = body.detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function getPortfolio(): Promise<Portfolio> {
  return request<Portfolio>("/api/portfolio");
}

export function getPortfolioHistory(): Promise<PortfolioSnapshot[]> {
  return request<PortfolioSnapshot[]>("/api/portfolio/history");
}

export function executeTrade(
  ticker: string,
  quantity: number,
  side: "buy" | "sell",
): Promise<{ trade: Trade; portfolio: Portfolio }> {
  return request("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker, quantity, side }),
  });
}

export function getWatchlist(): Promise<WatchlistItem[]> {
  return request<WatchlistItem[]>("/api/watchlist");
}

export function addToWatchlist(ticker: string): Promise<WatchlistItem> {
  return request<WatchlistItem>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export function removeFromWatchlist(ticker: string): Promise<void> {
  return request<void>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });
}

export function sendChatMessage(message: string): Promise<{
  message: string;
  trades: ChatTradeResult[];
  watchlist_changes: ChatWatchlistChangeResult[];
}> {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
