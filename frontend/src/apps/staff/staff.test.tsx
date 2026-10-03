import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IDLE_LOCK_MS } from "@/apps/staff/IdleLock";
import StaffArea from "@/apps/staff/StaffArea";
import { getAccessToken, setAccessToken } from "@/lib/auth";
import { envelope, json } from "@/test/fetch";
import { renderArea } from "@/test/render";
import { ME_MANAGER, ME_STAFF, serveApi, type Responder } from "@/test/server";

const DEVICE = "GET /api/v1/devices/current";
const SWITCH = "POST /api/v1/auth/pin-switch";

function currentDevice(locked = false) {
  return json({
    device: {
      id: "d1",
      name: "Front counter tablet",
      branch: { id: "b1", name: "Kilimani" },
      status: locked ? "locked" : "active",
    },
    locked,
    roster: [
      { id: "u1", first_name: "Wanjiru", last_initial: "K", role: "staff" },
      { id: "u2", first_name: "Juma", last_initial: "O", role: "manager" },
    ],
  });
}

function open(path: string) {
  return renderArea(path, [{ path: "/staff/*", element: <StaffArea /> }]);
}

const location = () => screen.getByTestId("location").textContent;

async function pressPin(user: ReturnType<typeof userEvent.setup>, pin: string) {
  for (const digit of pin) await user.click(screen.getByRole("button", { name: digit }));
}

beforeEach(() => setAccessToken(null));
afterEach(() => vi.useRealTimers());

describe("X-15 Switch user", () => {
  function serve(extra: Record<string, Responder> = {}) {
    return serveApi({ [DEVICE]: () => currentDevice(), ...extra });
  }

  it("is where signed-out people land on a registered device, with the branch's people", async () => {
    serve();
    open("/staff/queue");
    expect(
      await screen.findByRole("heading", { name: "Who's using this device?" }),
    ).toBeInTheDocument();
    expect(location()).toBe(`/staff/switch?returnTo=${encodeURIComponent("/staff/queue")}`);
    expect(screen.getByText("Front counter tablet · Kilimani")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Wanjiru K\./ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Juma O\./ })).toBeInTheDocument();
  });

  it("signs the chosen person in with their PIN and goes back where they were", async () => {
    const user = userEvent.setup();
    const api = serve({
      [SWITCH]: () => json({ access: "access-pin", user: { ...ME_STAFF, has_pin: true } }),
      "GET /api/v1/me": () => json({ ...ME_STAFF, has_pin: true }),
    });
    open("/staff/queue");
    await user.click(await screen.findByRole("button", { name: /Wanjiru K\./ }));
    expect(screen.getByRole("heading", { name: "Hi Wanjiru, enter your PIN" })).toBeInTheDocument();
    await pressPin(user, "4826");

    await waitFor(() => expect(location()).toBe("/staff/queue"));
    expect(getAccessToken()).toBe("access-pin");
    expect(await api.to(SWITCH)[0]?.json()).toEqual({ user_id: "u1", pin: "4826" });
  });

  it("says how many tries are left after a wrong PIN, and clears the dots", async () => {
    const user = userEvent.setup();
    serve({
      [SWITCH]: () =>
        json(envelope("wrong_pin", "That PIN isn't right.", { attempts_left: 3 }), 400),
    });
    open("/staff/switch");
    await user.click(await screen.findByRole("button", { name: /Wanjiru K\./ }));
    await pressPin(user, "1111");
    expect(await screen.findByRole("alert")).toHaveTextContent("That PIN isn't right.");
    expect(screen.getByText("3 tries left before this device locks.")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /0 of 4 digits/ })).toBeInTheDocument();
  });

  it("shows the lock when the fifth wrong PIN locks the device", async () => {
    const user = userEvent.setup();
    let locked = false;
    serveApi({
      [DEVICE]: () => currentDevice(locked),
      [SWITCH]: () => {
        locked = true;
        return json(
          envelope(
            "device_locked",
            "This device is locked. Ask a manager to sign in on it to unlock it.",
            { attempts_left: 0 },
          ),
          403,
        );
      },
    });
    open("/staff/switch");
    await user.click(await screen.findByRole("button", { name: /Wanjiru K\./ }));
    await pressPin(user, "1111");
    expect(
      await screen.findByText(
        "This device is locked. Ask a manager to sign in on it to unlock it.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "1" })).toBeNull();
    expect(screen.getByRole("link", { name: "Log in with password" })).toHaveAttribute(
      "href",
      "/staff/login",
    );
  });

  it("a locked device shows no people, only the way for a manager to unlock it", async () => {
    serveApi({ [DEVICE]: () => currentDevice(true) });
    open("/staff/switch");
    expect(
      await screen.findByText(
        "This device is locked. Ask a manager to sign in on it to unlock it.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Wanjiru/ })).toBeNull();
  });

  it("isn't available on an ordinary browser", async () => {
    serveApi({});
    open("/staff/switch");
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });
});

describe("idle lock", () => {
  it("locks a registered device after 5 idle minutes, ending the session", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    setAccessToken("access-pin");
    const api = serveApi({
      [DEVICE]: () => currentDevice(),
      "GET /api/v1/me": () => json({ ...ME_STAFF, has_pin: true }),
      "POST /api/v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    open("/staff");
    expect(await screen.findByRole("button", { name: "Switch user" })).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(IDLE_LOCK_MS - 1_000));
    fireEvent.pointerDown(window); // activity starts the 5 minutes again
    await act(() => vi.advanceTimersByTimeAsync(IDLE_LOCK_MS - 1_000));
    expect(getAccessToken()).toBe("access-pin");

    await act(() => vi.advanceTimersByTimeAsync(1_000));
    await waitFor(() => expect(location()).toBe("/staff/switch"));
    expect(getAccessToken()).toBeNull();
    expect(api.to("POST /api/v1/auth/logout")).toHaveLength(1);
  });

  it("never runs on an ordinary browser", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    setAccessToken("access-1");
    serveApi({ "GET /api/v1/me": () => json(ME_MANAGER) });
    open("/staff");
    expect(await screen.findByRole("button", { name: "Log out" })).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(IDLE_LOCK_MS * 2));
    expect(getAccessToken()).toBe("access-1");
  });
});

describe("S-02 Register this device", () => {
  it("lets a manager register the device, which signs them out onto X-15", async () => {
    const user = userEvent.setup();
    setAccessToken("access-manager");
    let registered = false;
    const api = serveApi({
      [DEVICE]: () => (registered ? currentDevice() : json(envelope("not_found", "x"), 404)),
      "GET /api/v1/me": () => json(ME_MANAGER),
      "GET /api/v1/me/branches": () => json([{ id: "b1", name: "Kilimani" }]),
      "POST /api/v1/staff/devices": () => {
        registered = true;
        return json(
          {
            id: "d1",
            name: "Front counter tablet",
            branch: { id: "b1", name: "Kilimani" },
            status: "active",
          },
          201,
        );
      },
    });
    open("/staff");
    await user.click(await screen.findByRole("link", { name: "Register this device" }));
    expect(await screen.findByRole("radio", { name: "Kilimani" })).toBeChecked(); // the only branch
    expect(
      screen.getByText(
        "Registering signs you out of this device. After that, people at this branch switch in with their PINs.",
      ),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Device name"), "Front counter tablet");
    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(
      await screen.findByRole("heading", { name: "Who's using this device?" }),
    ).toBeInTheDocument();
    expect(location()).toBe("/staff/switch");
    expect(getAccessToken()).toBeNull();
    const request = api.to("POST /api/v1/staff/devices")[0];
    expect(await request?.json()).toEqual({ name: "Front counter tablet", branch_id: "b1" });
    expect(request?.headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("needs a name", async () => {
    const user = userEvent.setup();
    setAccessToken("access-manager");
    const api = serveApi({
      "GET /api/v1/me": () => json(ME_MANAGER),
      "GET /api/v1/me/branches": () => json([{ id: "b1", name: "Kilimani" }]),
    });
    open("/staff/register-device");
    await user.click(await screen.findByRole("button", { name: "Register" }));
    expect(await screen.findByText("Give the device a name.")).toBeInTheDocument();
    expect(api.to("POST /api/v1/staff/devices")).toHaveLength(0);
  });

  it("is not there for staff", async () => {
    setAccessToken("access-staff");
    serveApi({
      "GET /api/v1/me": () => json(ME_STAFF),
      "GET /api/v1/me/branches": () => json([{ id: "b1", name: "Kilimani" }]),
    });
    open("/staff/register-device");
    expect(
      await screen.findByRole("heading", { name: "We couldn't find that" }),
    ).toBeInTheDocument();
  });

  it("isn't offered to staff on the home screen", async () => {
    setAccessToken("access-staff");
    serveApi({ "GET /api/v1/me": () => json(ME_STAFF) });
    open("/staff");
    expect(await screen.findByText("Signed in as Wanjiru K.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Register this device" })).toBeNull();
  });
});
