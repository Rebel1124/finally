"use client";

import type { ConnectionStatus } from "@/lib/usePriceStream";
import { formatCurrency } from "@/lib/format";

const STATUS_STYLES: Record<ConnectionStatus, { color: string; label: string }> = {
  open: { color: "bg-up", label: "Connected" },
  reconnecting: { color: "bg-accent-yellow", label: "Reconnecting" },
  connecting: { color: "bg-down", label: "Connecting" },
};

interface HeaderProps {
  totalValue: number;
  equity: number;
  cashBalance: number;
  status: ConnectionStatus;
}

export default function Header({ totalValue, equity, cashBalance, status }: HeaderProps) {
  const { color, label } = STATUS_STYLES[status];

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-6 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-semibold tracking-tight text-accent-yellow">
          FinAlly
        </span>
        <span className="text-xs text-muted">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-8 font-mono">
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-muted">
            Portfolio Value
          </div>
          <div className="text-lg font-semibold">{formatCurrency(totalValue)}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-muted">Equity</div>
          <div className="text-lg font-semibold text-accent-yellow">
            {formatCurrency(equity)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-muted">Cash</div>
          <div className="text-lg font-semibold text-accent-blue">
            {formatCurrency(cashBalance)}
          </div>
        </div>
        <div className="flex items-center gap-2" title={label}>
          <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
          <span className="text-xs text-muted">{label}</span>
        </div>
      </div>
    </header>
  );
}
