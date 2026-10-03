import { fireEvent, render, screen } from "@testing-library/react";

import { X02UpdateRequired } from "@/apps/shared/screens/X02UpdateRequired";
import { X04NotFound } from "@/apps/shared/screens/X04NotFound";

describe("X-02", () => {
  it("has one way forward: update", () => {
    const onUpdate = vi.fn();
    render(<X02UpdateRequired onUpdate={onUpdate} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Update now" }));
    expect(onUpdate).toHaveBeenCalledTimes(1);
  });
});

describe("X-04", () => {
  it("goes back to the app's home", () => {
    const onHome = vi.fn();
    render(<X04NotFound homePath="/staff" onHome={onHome} />);
    expect(screen.getByRole("heading", { name: "We couldn't find that" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to home" }));
    expect(onHome).toHaveBeenCalledWith("/staff");
  });
});
