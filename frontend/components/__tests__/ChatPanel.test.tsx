import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPanel from "../ChatPanel";
import type { ChatMessage } from "@/lib/types";

const messages: ChatMessage[] = [
  { id: "1", role: "user", content: "buy 10 apple" },
  {
    id: "2",
    role: "assistant",
    content: "Bought 10 shares of AAPL.",
    trades: [{ ticker: "AAPL", side: "buy", quantity: 10, price: 190.5, status: "executed" }],
  },
];

describe("ChatPanel", () => {
  it("renders conversation history and trade confirmations", () => {
    render(<ChatPanel messages={messages} onSend={async () => {}} />);

    expect(screen.getByText("buy 10 apple")).toBeInTheDocument();
    expect(screen.getByText("Bought 10 shares of AAPL.")).toBeInTheDocument();
    expect(screen.getByText(/10 AAPL @ \$190\.50/)).toBeInTheDocument();
  });

  it("shows a loading indicator while awaiting a response", async () => {
    let resolveSend: () => void = () => {};
    const onSend = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSend = resolve;
        }),
    );

    render(<ChatPanel messages={[]} onSend={onSend} />);

    fireEvent.change(screen.getByPlaceholderText("Ask FinAlly…"), {
      target: { value: "how is my portfolio doing" },
    });
    fireEvent.click(screen.getByText("Send"));

    expect(await screen.findByText("Thinking…")).toBeInTheDocument();

    resolveSend();
    await waitFor(() => expect(screen.queryByText("Thinking…")).not.toBeInTheDocument());
  });
});
