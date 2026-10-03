import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { PinKeypad } from "@/components/PinKeypad";

function Harness({ onComplete }: { onComplete: (pin: string) => void }) {
  const [pin, setPin] = useState("");
  return <PinKeypad label="PIN" value={pin} onChange={setPin} onComplete={onComplete} />;
}

describe("PinKeypad", () => {
  it("fills from the keys, never shows the digits, and completes on the fourth", () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    for (const digit of "482") fireEvent.click(screen.getByRole("button", { name: digit }));
    expect(screen.getByRole("status", { name: "PIN: 3 of 4 digits entered" })).toBeInTheDocument();
    expect(screen.queryByText("482")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete the last digit" }));
    fireEvent.click(screen.getByRole("button", { name: "6" }));
    fireEvent.click(screen.getByRole("button", { name: "1" }));
    expect(onComplete).toHaveBeenCalledWith("4861");
  });

  it("works with a physical keyboard", () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    for (const key of ["4", "8", "Backspace", "2", "6", "1"]) fireEvent.keyDown(window, { key });
    expect(onComplete).toHaveBeenCalledWith("4261");
  });
});
