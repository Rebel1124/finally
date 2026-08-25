"use client";

import { useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (message: string) => Promise<void>;
}

export default function ChatPanel({ messages, onSend }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    try {
      await onSend(text);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          AI Assistant
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2">
        {messages.length === 0 && (
          <p className="text-sm text-muted">
            Ask FinAlly about your portfolio, or tell it to make a trade.
          </p>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "ml-6 bg-accent-blue/15 text-foreground"
                  : "mr-6 bg-white/5 text-foreground"
              }`}
            >
              <p>{msg.content}</p>
              {(msg.trades?.length || msg.watchlistChanges?.length) ? (
                <div className="mt-2 flex flex-col gap-1 border-t border-border/60 pt-2">
                  {msg.trades?.map((t, i) => (
                    <span key={`trade-${i}`} className="text-xs text-muted">
                      {t.status === "executed" ? (
                        <>
                          <span className={t.side === "buy" ? "text-up" : "text-down"}>
                            {t.side === "buy" ? "Bought" : "Sold"}
                          </span>{" "}
                          {t.quantity} {t.ticker} @ {formatCurrency(t.price ?? 0)}
                        </>
                      ) : (
                        <span className="text-down">
                          {t.ticker}: {t.status}
                        </span>
                      )}
                    </span>
                  ))}
                  {msg.watchlistChanges?.map((w, i) => (
                    <span key={`wl-${i}`} className="text-xs text-muted">
                      {w.status === "executed" ? (
                        <>
                          {w.action === "add" ? "Added" : "Removed"} {w.ticker} to
                          watchlist
                        </>
                      ) : (
                        <span className="text-down">
                          {w.ticker}: {w.status}
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
          {loading && (
            <div className="mr-6 rounded-lg bg-white/5 px-3 py-2 text-sm text-muted">
              Thinking…
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FinAlly…"
          className="flex-1 rounded border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent-blue"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded bg-accent-purple px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
