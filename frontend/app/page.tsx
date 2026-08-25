"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import { makeId } from "@/lib/id";
import { usePriceStream } from "@/lib/usePriceStream";
import type { ChatMessage, Portfolio, PortfolioSnapshot, WatchlistItem } from "@/lib/types";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import PortfolioHeatmap from "@/components/PortfolioHeatmap";
import PnLChart from "@/components/PnLChart";
import PositionsTable from "@/components/PositionsTable";
import TradeBar from "@/components/TradeBar";
import ChatPanel from "@/components/ChatPanel";

const EMPTY_PORTFOLIO: Portfolio = { cash_balance: 0, positions: [], total_value: 0 };

export default function Home() {
  const { prices, history, status } = usePriceStream();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [portfolioHistory, setPortfolioHistory] = useState<PortfolioSnapshot[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // Cash only changes when a trade executes (comes straight from the last
  // portfolio fetch), but position values should track live SSE prices tick
  // by tick so the header and portfolio views move with the market between
  // trades, not just after them.
  const livePositions = useMemo(
    () =>
      portfolio.positions.map((p) => {
        const livePrice = prices[p.ticker]?.price ?? p.current_price;
        const marketValue = p.quantity * livePrice;
        const unrealizedPnl = marketValue - p.quantity * p.avg_cost;
        const unrealizedPnlPercent =
          p.avg_cost && p.quantity ? (unrealizedPnl / (p.quantity * p.avg_cost)) * 100 : 0;
        return {
          ...p,
          current_price: livePrice,
          market_value: marketValue,
          unrealized_pnl: unrealizedPnl,
          unrealized_pnl_percent: unrealizedPnlPercent,
        };
      }),
    [portfolio.positions, prices],
  );
  const equity = useMemo(
    () => livePositions.reduce((sum, p) => sum + p.market_value, 0),
    [livePositions],
  );
  const liveTotalValue = portfolio.cash_balance + equity;

  const refreshPortfolio = useCallback(() => {
    Promise.all([api.getPortfolio(), api.getPortfolioHistory()])
      .then(([p, h]) => {
        setPortfolio(p);
        setPortfolioHistory(h);
      })
      .catch(() => {
        // backend not reachable yet; keep prior state
      });
  }, []);

  useEffect(() => {
    api
      .getWatchlist()
      .then((items) => {
        setWatchlist(items);
        if (items.length > 0) setSelectedTicker((prev) => prev ?? items[0].ticker);
      })
      .catch(() => {});
    refreshPortfolio();
  }, [refreshPortfolio]);

  async function handleAddTicker(ticker: string) {
    const item = await api.addToWatchlist(ticker);
    setWatchlist((prev) =>
      prev.some((w) => w.ticker === item.ticker) ? prev : [...prev, item],
    );
  }

  async function handleRemoveTicker(ticker: string) {
    await api.removeFromWatchlist(ticker);
    setWatchlist((prev) => prev.filter((w) => w.ticker !== ticker));
    setSelectedTicker((prev) => (prev === ticker ? null : prev));
  }

  async function handleTrade(ticker: string, quantity: number, side: "buy" | "sell") {
    const { portfolio: updated } = await api.executeTrade(ticker, quantity, side);
    setPortfolio(updated);
    refreshPortfolio();
  }

  async function handleChatSend(message: string) {
    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: message,
    };
    setChatMessages((prev) => [...prev, userMessage]);

    const response = await api.sendChatMessage(message);
    const assistantMessage: ChatMessage = {
      id: makeId(),
      role: "assistant",
      content: response.message,
      trades: response.trades,
      watchlistChanges: response.watchlist_changes,
    };
    setChatMessages((prev) => [...prev, assistantMessage]);

    if (response.trades.length > 0) {
      refreshPortfolio();
    }
    if (response.watchlist_changes.some((w) => w.status === "executed")) {
      api.getWatchlist().then(setWatchlist).catch(() => {});
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header
        totalValue={liveTotalValue}
        equity={equity}
        cashBalance={portfolio.cash_balance}
        status={status}
      />

      <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr_360px]">
        <aside className="min-h-0 border-r border-border bg-panel">
          <Watchlist
            tickers={watchlist}
            prices={prices}
            history={history}
            selectedTicker={selectedTicker}
            onSelect={setSelectedTicker}
            onAdd={handleAddTicker}
            onRemove={handleRemoveTicker}
          />
        </aside>

        <main className="grid min-h-0 grid-rows-[2fr_1fr_1fr_auto]">
          <MainChart ticker={selectedTicker} data={selectedTicker ? (history[selectedTicker] ?? []) : []} />
          <div className="grid min-h-0 grid-cols-2 border-b border-border">
            <div className="min-h-0 border-r border-border">
              <PortfolioHeatmap positions={livePositions} />
            </div>
            <div className="min-h-0">
              <PnLChart snapshots={portfolioHistory} />
            </div>
          </div>
          <div className="min-h-0 border-b border-border">
            <PositionsTable
              positions={livePositions}
              selectedTicker={selectedTicker}
              onSelect={setSelectedTicker}
            />
          </div>
          <TradeBar defaultTicker={selectedTicker} onTrade={handleTrade} />
        </main>

        <aside className="min-h-0 border-l border-border bg-panel">
          <ChatPanel messages={chatMessages} onSend={handleChatSend} />
        </aside>
      </div>
    </div>
  );
}
