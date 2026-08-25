import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import TradeBar from "../TradeBar";

describe("TradeBar", () => {
  it("shows a validation error and does not call onTrade when fields are empty", () => {
    const onTrade = vi.fn();
    render(<TradeBar defaultTicker={null} onTrade={onTrade} />);

    fireEvent.click(screen.getByText("Sell"));

    expect(screen.getByText("Enter a ticker")).toBeInTheDocument();
    expect(onTrade).not.toHaveBeenCalled();
  });

  it("shows a validation error when quantity is missing", () => {
    const onTrade = vi.fn();
    render(<TradeBar defaultTicker={null} onTrade={onTrade} />);

    fireEvent.change(screen.getByPlaceholderText("Ticker"), {
      target: { value: "MSFT" },
    });
    fireEvent.click(screen.getByText("Sell"));

    expect(screen.getByText("Enter a quantity")).toBeInTheDocument();
    expect(onTrade).not.toHaveBeenCalled();
  });

  it("prefills the ticker input when defaultTicker changes", () => {
    const { rerender } = render(<TradeBar defaultTicker={null} onTrade={async () => {}} />);
    expect(screen.getByPlaceholderText("Ticker")).toHaveValue("");

    rerender(<TradeBar defaultTicker="MSFT" onTrade={async () => {}} />);
    expect(screen.getByPlaceholderText("Ticker")).toHaveValue("MSFT");
  });

  it("submits a trade once ticker and quantity are filled in", () => {
    const onTrade = vi.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker="MSFT" onTrade={onTrade} />);

    fireEvent.change(screen.getByPlaceholderText("Qty"), {
      target: { value: "5" },
    });
    fireEvent.click(screen.getByText("Sell"));

    expect(onTrade).toHaveBeenCalledWith("MSFT", 5, "sell");
  });
});
