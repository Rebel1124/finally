export type Direction = "up" | "down" | "flat";

export interface PriceTick {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: Direction;
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: Direction | null;
  added_at: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  total_value: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export interface Trade {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  executed_at: string;
}

export interface ChatTradeResult {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price?: number;
  status: string;
}

export interface ChatWatchlistChangeResult {
  ticker: string;
  action: "add" | "remove";
  status: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trades?: ChatTradeResult[];
  watchlistChanges?: ChatWatchlistChangeResult[];
}
