import { act, fireEvent, render, screen } from "@testing-library/react";

import { ApiError } from "@/api/errors";
import { Button } from "@/components/Button";
import {
  FirstLoad,
  OfflineBanner,
  RefreshBar,
  ServerErrorBanner,
  Throttled,
} from "@/components/states";
import { reportNetworkFailure, reportNetworkSuccess } from "@/lib/online";

afterEach(() => vi.useRealTimers());

describe("FirstLoad", () => {
  it("shows nothing for 200 ms, then the skeleton", () => {
    vi.useFakeTimers();
    render(<FirstLoad skeleton={<div data-testid="skeleton" />} />);
    expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    act(() => vi.advanceTimersByTime(199));
    expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId("skeleton")).toBeInTheDocument();
  });
});

describe("RefreshBar", () => {
  it("shows only while refreshing", () => {
    const { rerender } = render(<RefreshBar active={false} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    rerender(<RefreshBar active />);
    expect(screen.getByRole("progressbar", { name: "Updating" })).toBeInTheDocument();
  });
});

describe("ServerErrorBanner", () => {
  it("says what happened, offers Retry and shows a short reference", () => {
    const onRetry = vi.fn();
    const error = new ApiError({
      status: 500,
      code: "server_error",
      message: "Something went wrong on our side. Please try again.",
      requestId: "3f2a9c1be0d84e6f9a7b5c3d2e1f0a9b",
    });
    render(<ServerErrorBanner error={error} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Something went wrong on our side. Please try again.",
    );
    expect(screen.getByText("Reference: 3F2A9C1B")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows the connection message for network failures", () => {
    render(<ServerErrorBanner error={ApiError.network()} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "We couldn't connect. Check your internet connection and try again.",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("OfflineBanner", () => {
  afterEach(() => {
    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => true });
    act(() => reportNetworkSuccess());
  });

  it("appears when the browser goes offline and goes when it's back", () => {
    render(<OfflineBanner />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => false });
    act(() => window.dispatchEvent(new Event("offline")));
    expect(screen.getByRole("status")).toHaveTextContent("You're offline.");

    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => true });
    act(() => window.dispatchEvent(new Event("online")));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("appears when requests fail even though the browser says online", () => {
    render(<OfflineBanner />);
    act(() => reportNetworkFailure());
    expect(screen.getByRole("status")).toHaveTextContent("You're offline.");
    act(() => reportNetworkSuccess());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("Throttled", () => {
  it("counts down in minutes, then seconds, then lets the user try again", () => {
    vi.useFakeTimers();
    const onDone = vi.fn();
    render(<Throttled retryAfter={170} onDone={onDone} />);
    expect(screen.getByText("Too many attempts. Try again in 3 minutes.")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Too many attempts. Try again in 2 minutes.")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(50_000));
    expect(screen.getByText("Too many attempts. Try again in 1 minute.")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByText("Too many attempts. Try again in 59 seconds.")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(58_000));
    expect(screen.getByText("Too many attempts. Try again in 1 second.")).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.queryByText(/Too many attempts/)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(5_000));
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});

describe("Button", () => {
  it("is disabled and busy while submitting, with a spoken label", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveTextContent("Please wait");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is a plain button by default, so it never submits a form by accident", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "button");
  });
});
