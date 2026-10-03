import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PlaceholderArea } from "@/apps/PlaceholderArea";
import { meQueryKey, resetFlow } from "@/apps/shared/signin/session";
import { SignInRoutes } from "@/apps/shared/signin/SignInRoutes";
import { getAccessToken, setAccessToken } from "@/lib/auth";
import { envelope, json, mockFetch, pathOf } from "@/test/fetch";
import { renderArea } from "@/test/render";

const ME = {
  id: "7d3c1d64-8a52-4e63-9d0c-0d7c1c5b8a11",
  phone: "+254712345678",
  first_name: "Wanjiru",
  last_name: "Kamau",
  role: "staff",
  language: "en",
  is_phone_verified: true,
  rights: { accept_cash: false, give_discounts: false, correct_prices: false },
  has_pin: true,
};

type Responder = (request: Request) => Response | Promise<Response>;

function serve(routes: Record<string, Responder>) {
  return mockFetch((request) => {
    const responder = routes[pathOf(request)];
    return responder ? responder(request) : json(envelope("not_found", "x"), 404);
  });
}

function open(path: string) {
  return renderArea(path, [
    {
      path: "/staff/*",
      element: <SignInRoutes app="staff" signedIn={<PlaceholderArea area="staff" />} />,
    },
  ]);
}

const location = () => screen.getByTestId("location").textContent;

beforeEach(() => {
  setAccessToken(null);
  resetFlow.clear();
});
afterEach(() => vi.useRealTimers());

describe("guards", () => {
  it("sends signed-out visitors to X-10 and remembers where they were going", async () => {
    open("/staff/queue?tab=ready");
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(location()).toBe(
      `/staff/login?returnTo=${encodeURIComponent("/staff/queue?tab=ready")}`,
    );
  });

  it("sends someone already signed in from X-10 to the app's home", async () => {
    setAccessToken("token");
    open("/staff/login");
    expect(await screen.findByRole("heading", { name: "Staff app" })).toBeInTheDocument();
  });
});

describe("X-10 Log in", () => {
  it("shows the business, and Log in stays disabled until both fields are filled", async () => {
    const user = userEvent.setup();
    open("/staff/login");
    expect(screen.getByText("Mama Safi")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Log in" });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    expect(button).toBeEnabled();
  });

  it("signs in and goes back to the page the user was trying to reach", async () => {
    const user = userEvent.setup();
    const { requests } = serve({
      "/api/v1/auth/login": () => json({ access: "access-1", user: ME }),
    });
    const { queryClient } = open(`/staff/login?returnTo=${encodeURIComponent("/staff/queue")}`);

    await user.type(screen.getByLabelText("Phone number"), "0712 345 678");
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(location()).toBe("/staff/queue"));
    expect(getAccessToken()).toBe("access-1");
    expect(queryClient.getQueryData(meQueryKey)).toEqual(ME);
    expect(await requests[0]?.json()).toEqual({ phone: "0712 345 678", password: "s3cret-pass" });
  });

  it("never follows a returnTo off the site", async () => {
    const user = userEvent.setup();
    serve({ "/api/v1/auth/login": () => json({ access: "a", user: ME }) });
    open(`/staff/login?returnTo=${encodeURIComponent("https://evil.example/")}`);
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(location()).toBe("/staff"));
  });

  it("says the phone number or password is incorrect, never which, and keeps the input", async () => {
    const user = userEvent.setup();
    serve({
      "/api/v1/auth/login": () =>
        json(envelope("invalid_credentials", "Phone number or password is incorrect"), 400),
    });
    open("/staff/login");
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.type(screen.getByLabelText("Password"), "wrong-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Phone number or password is incorrect",
    );
    expect(screen.getByLabelText("Phone number")).toHaveValue("0712345678");
    expect(screen.getByLabelText("Password")).toHaveValue("wrong-pass");
    expect(getAccessToken()).toBeNull();
  });

  it("shows the suspension message with the business's support contact", async () => {
    const user = userEvent.setup();
    const message = "Your account is suspended. Contact Mama Safi Laundry on 0712 345 678";
    serve({ "/api/v1/auth/login": () => json(envelope("account_suspended", message), 403) });
    open("/staff/login");
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("checks the phone number's shape before asking the server", async () => {
    const user = userEvent.setup();
    const { spy } = serve({});
    open("/staff/login");
    await user.type(screen.getByLabelText("Phone number"), "12345");
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(
      await screen.findByText("Enter a Kenyan mobile number, like 0712 345 678."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Phone number")).toHaveFocus();
    expect(spy).not.toHaveBeenCalled();
  });

  it("counts down when throttled and keeps Log in disabled meanwhile", async () => {
    const user = userEvent.setup();
    serve({
      "/api/v1/auth/login": () =>
        json(
          envelope("throttled", "Too many attempts. Try again in 15 minutes.", {
            retry_after: 900,
          }),
          429,
        ),
    });
    open("/staff/login");
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.type(screen.getByLabelText("Password"), "s3cret-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(
      await screen.findByText("Too many attempts. Try again in 15 minutes."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeDisabled();
  });

  it("links to Forgot password", async () => {
    const user = userEvent.setup();
    open("/staff/login");
    await user.click(screen.getByRole("link", { name: "Forgot password?" }));
    expect(await screen.findByRole("heading", { name: "Forgot password" })).toBeInTheDocument();
  });
});

describe("Forgot password: X-11, X-12, X-13", () => {
  const SENT = "If this number has an account, we've sent a code";

  async function reachCode(user: ReturnType<typeof userEvent.setup>) {
    open("/staff/forgot-password");
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByRole("heading", { name: "Enter code" });
  }

  function codeBoxes() {
    return screen.getAllByRole("textbox", { name: /Digit \d of 6/ });
  }

  it("X-11 always gives the same answer, then X-12 shows where the code went", async () => {
    const user = userEvent.setup();
    serve({ "/api/v1/auth/password-reset/request": () => json({ message: SENT }) });
    await reachCode(user);
    expect(screen.getByText(SENT)).toBeInTheDocument();
    expect(screen.getByText("Enter the 6-digit code sent to 0712 345 678")).toBeInTheDocument();
  });

  it("X-12 submits by itself on the sixth digit, then X-13 sets the password and signs in", async () => {
    const user = userEvent.setup();
    const { requests } = serve({
      "/api/v1/auth/password-reset/request": () => json({ message: SENT }),
      "/api/v1/auth/password-reset/verify": () => json({ reset_token: "grant-1" }),
      "/api/v1/auth/password-reset/confirm": () => json({ access: "access-2", user: ME }),
    });
    await reachCode(user);

    await user.type(codeBoxes()[0]!, "482916");
    expect(await screen.findByRole("heading", { name: "Set new password" })).toBeInTheDocument();
    const verifies = requests.filter((r) => pathOf(r).endsWith("/verify"));
    expect(verifies).toHaveLength(1);
    expect(await verifies[0]?.json()).toEqual({ phone: "0712345678", code: "482916" });

    await user.type(screen.getByLabelText("New password"), "kahawa-tamu");
    await user.type(screen.getByLabelText("Confirm password"), "kahawa-tamu");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(location()).toBe("/staff"));
    expect(getAccessToken()).toBe("access-2");
    const confirm = requests.find((r) => pathOf(r).endsWith("/confirm"));
    expect(await confirm?.json()).toEqual({ reset_token: "grant-1", password: "kahawa-tamu" });
    expect(resetFlow.get()).toBeNull();
  });

  it("X-12 fills every box from a paste", async () => {
    const user = userEvent.setup();
    serve({
      "/api/v1/auth/password-reset/request": () => json({ message: SENT }),
      "/api/v1/auth/password-reset/verify": () => json({ reset_token: "grant-1" }),
    });
    await reachCode(user);
    codeBoxes()[0]!.focus();
    await user.paste("48 29 16");
    expect(await screen.findByRole("heading", { name: "Set new password" })).toBeInTheDocument();
  });

  it("X-12 moves back with Backspace", async () => {
    const user = userEvent.setup();
    serve({ "/api/v1/auth/password-reset/request": () => json({ message: SENT }) });
    await reachCode(user);
    await user.type(codeBoxes()[0]!, "482");
    await user.keyboard("{Backspace}{Backspace}");
    expect(codeBoxes().map((box) => (box as HTMLInputElement).value)).toEqual([
      "4",
      "",
      "",
      "",
      "",
      "",
    ]);
    expect(codeBoxes()[1]).toHaveFocus();
  });

  it("X-12 shows attempts left only after the third wrong try", async () => {
    const user = userEvent.setup();
    let left = 5;
    serve({
      "/api/v1/auth/password-reset/request": () => json({ message: SENT }),
      "/api/v1/auth/password-reset/verify": () => {
        left -= 1;
        return json(
          envelope("invalid_code", "That code isn't right. Check the SMS and try again.", {
            attempts_left: left,
          }),
          400,
        );
      },
    });
    await reachCode(user);

    await user.type(codeBoxes()[0]!, "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That code isn't right. Check the SMS and try again.",
    );
    expect(screen.queryByText(/attempts? left/)).not.toBeInTheDocument();
    // What was typed stays; changing the last digit tries again.
    expect(codeBoxes()[5]).toHaveValue("1");

    await user.click(codeBoxes()[5]!);
    await user.keyboard("2");
    await waitFor(() => expect(left).toBe(3));
    await user.click(codeBoxes()[5]!);
    await user.keyboard("3");
    expect(await screen.findByText("2 attempts left")).toBeInTheDocument();
  });

  it("X-12 stops when the code is dead and asks for a new one", async () => {
    const user = userEvent.setup();
    serve({
      "/api/v1/auth/password-reset/request": () => json({ message: SENT }),
      "/api/v1/auth/password-reset/verify": () =>
        json(
          envelope("code_locked", "Too many wrong tries. Ask for a new code.", {
            attempts_left: 0,
          }),
          400,
        ),
    });
    await reachCode(user);
    await user.type(codeBoxes()[0]!, "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many wrong tries. Ask for a new code.",
    );
    codeBoxes().forEach((box) => expect(box).toBeDisabled());
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("X-12 lets the user resend after 60 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
    const { requests } = serve({
      "/api/v1/auth/password-reset/request": () => json({ message: SENT }),
    });
    await reachCode(user);

    expect(screen.getByText(/^Resend code in \d+s$/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resend code" })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(60_000));
    fireEvent.click(await screen.findByRole("button", { name: "Resend code" }));

    expect(await screen.findByText("We've sent a new code.")).toBeInTheDocument();
    expect(requests.filter((r) => pathOf(r).endsWith("/request"))).toHaveLength(2);
    expect(screen.getByText(/^Resend code in \d+s$/)).toBeInTheDocument();
  });

  it("X-12 Wrong number goes back to X-11 with the number filled in", async () => {
    const user = userEvent.setup();
    serve({ "/api/v1/auth/password-reset/request": () => json({ message: SENT }) });
    await reachCode(user);
    await user.click(screen.getByRole("button", { name: "Wrong number? Change it" }));
    expect(await screen.findByRole("heading", { name: "Forgot password" })).toBeInTheDocument();
    expect(screen.getByLabelText("Phone number")).toHaveValue("0712345678");
  });

  it("X-12 and X-13 opened directly (after a reload) start again at X-11", async () => {
    open("/staff/forgot-password/new-password");
    expect(await screen.findByRole("heading", { name: "Forgot password" })).toBeInTheDocument();
  });

  it("X-13 shows the live checklist and refuses mismatched passwords", async () => {
    const user = userEvent.setup();
    resetFlow.start("0712345678", SENT);
    resetFlow.setToken("grant-1");
    const { spy } = serve({});
    open("/staff/forgot-password/new-password");

    const save = screen.getByRole("button", { name: "Save" });
    const rules = screen.getByRole("list", { name: "Your password needs" });
    expect(rules).toHaveTextContent("At least 8 characters");
    expect(rules).toHaveTextContent("Not a common password");
    expect(rules).toHaveTextContent("Checked when you save");

    await user.type(screen.getByLabelText("New password"), "12345678");
    await user.type(screen.getByLabelText("Confirm password"), "12345678");
    expect(save).toBeDisabled(); // only numbers

    await user.clear(screen.getByLabelText("New password"));
    await user.type(screen.getByLabelText("New password"), "kahawa-tamu");
    expect(save).toBeEnabled();
    await user.click(save);
    expect(await screen.findByText("The passwords don't match.")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("X-13 shows the server's password rule under the field", async () => {
    const user = userEvent.setup();
    resetFlow.start("0712345678", SENT);
    resetFlow.setToken("grant-1");
    serve({
      "/api/v1/auth/password-reset/confirm": () =>
        json(
          envelope("validation_error", "Some details need fixing. Check the highlighted fields.", {
            fields: { password: ["This password is too common."] },
          }),
          400,
        ),
    });
    open("/staff/forgot-password/new-password");
    await user.type(screen.getByLabelText("New password"), "password1");
    await user.type(screen.getByLabelText("Confirm password"), "password1");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("This password is too common.")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toHaveValue("password1");
  });

  it("X-13 starts again at X-11 when the reset has expired, saying why", async () => {
    const user = userEvent.setup();
    resetFlow.start("0712345678", SENT);
    resetFlow.setToken("grant-1");
    const expired = "This reset has expired. Start again from Forgot password.";
    serve({
      "/api/v1/auth/password-reset/confirm": () =>
        json(envelope("invalid_reset_token", expired), 400),
    });
    open("/staff/forgot-password/new-password");
    await user.type(screen.getByLabelText("New password"), "kahawa-tamu");
    await user.type(screen.getByLabelText("Confirm password"), "kahawa-tamu");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("heading", { name: "Forgot password" })).toBeInTheDocument();
    expect(screen.getByText(expired)).toBeInTheDocument();
  });
});
