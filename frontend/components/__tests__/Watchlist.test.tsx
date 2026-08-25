import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Watchlist from "../Watchlist";
import type { PriceTick, WatchlistItem } from "@/lib/types";

const baseTicker: WatchlistItem = {
  ticker: "AAPL",
  price: 190.5,
  previous_price: 189.9,
  change: 0.6,
  change_percent: 0.32,
  direction: "up",
  added_at: "2026-08-25T12:00:00Z",
};

function tick(price: number): PriceTick {
  return {
    ticker: "AAPL",
    price,
    previous_price: 189.9,
    timestamp: 1234.5,
    change: price - 189.9,
    change_percent: 0.32,
    direction: "up",
  };
}

describe("Watchlist", () => {
  it("applies a flash class when a tracked price changes", () => {
    const { rerender, getByText } = render(
      <Watchlist
        tickers={[baseTicker]}
        prices={{ AAPL: tick(190.5) }}
        history={{}}
        selectedTicker={null}
        onSelect={() => {}}
        onAdd={async () => {}}
        onRemove={async () => {}}
      />,
    );

    expect(getByText("190.50").className).not.toContain("flash-up");

    rerender(
      <Watchlist
        tickers={[baseTicker]}
        prices={{ AAPL: tick(191.25) }}
        history={{}}
        selectedTicker={null}
        onSelect={() => {}}
        onAdd={async () => {}}
        onRemove={async () => {}}
      />,
    );

    expect(getByText("191.25").className).toContain("flash-up");
  });

  it("submits a new ticker via the add form", () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(
      <Watchlist
        tickers={[]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={() => {}}
        onAdd={onAdd}
        onRemove={async () => {}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Ticker"), {
      target: { value: "pypl" },
    });
    fireEvent.click(screen.getByText("Add"));

    expect(onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("removes a ticker when the remove button is clicked", () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    render(
      <Watchlist
        tickers={[baseTicker]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={() => {}}
        onAdd={async () => {}}
        onRemove={onRemove}
      />,
    );

    fireEvent.click(screen.getByLabelText("Remove AAPL"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });
});
