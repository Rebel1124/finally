import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import PositionsTable from "../PositionsTable";
import type { Position } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 185,
    current_price: 190.5,
    market_value: 1905,
    unrealized_pnl: 55,
    unrealized_pnl_percent: 2.97,
  },
];

describe("PositionsTable", () => {
  it("renders position numbers from portfolio data", () => {
    render(<PositionsTable positions={positions} />);

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("185.00")).toBeInTheDocument();
    expect(screen.getByText("190.50")).toBeInTheDocument();
    expect(screen.getByText("$55.00")).toBeInTheDocument();
    expect(screen.getByText("+2.97%")).toBeInTheDocument();
  });

  it("shows an empty state with no positions", () => {
    render(<PositionsTable positions={[]} />);
    expect(screen.getByText("No positions yet")).toBeInTheDocument();
  });

  it("calls onSelect with the ticker when a row is clicked", () => {
    const onSelect = vi.fn();
    render(<PositionsTable positions={positions} onSelect={onSelect} />);

    fireEvent.click(screen.getByText("AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });
});
