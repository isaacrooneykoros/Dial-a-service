import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { inviteFlow } from "@/apps/shared/invite/inviteFlow";
import { InviteRoutes } from "@/apps/shared/invite/InviteRoutes";
import { getAccessToken, setAccessToken } from "@/lib/auth";
import { envelope, json } from "@/test/fetch";
import { renderArea } from "@/test/render";
import { ME_STAFF, serveApi } from "@/test/server";

const TOKEN = "Zk3pQ9";
const DETAIL = `GET /api/v1/auth/invitations/${TOKEN}`;
const SEND = `POST /api/v1/auth/invitations/${TOKEN}/send-code`;
const VERIFY = `POST /api/v1/auth/invitations/${TOKEN}/verify`;
const ACCEPT = "POST /api/v1/auth/invitations/accept";

function invitation(role = "staff", role_label = "Shop staff") {
  return json({
    business_name: "Mama Safi Laundry",
    role,
    role_label,
    first_name: "Wanjiru",
    phone: "+254712345678",
  });
}

function open(path = `/invite/${TOKEN}`) {
  return renderArea(path, [
    { path: "/invite/*", element: <InviteRoutes /> },
    { path: "/staff/*", element: <h1>Staff home</h1> },
    { path: "/console/*", element: <h1>Console home</h1> },
  ]);
}

const location = () => screen.getByTestId("location").textContent;

async function pressPin(user: ReturnType<typeof userEvent.setup>, pin: string) {
  for (const digit of pin) await user.click(screen.getByRole("button", { name: digit }));
}

beforeEach(() => {
  setAccessToken(null);
  inviteFlow.clear();
});

describe("X-14 Accept invitation", () => {
  it("says who invited them as what, shows the number read-only, and sends a code", async () => {
    const user = userEvent.setup();
    serveApi({
      [DETAIL]: () => invitation(),
      [SEND]: () => json({ message: "We've sent a code to your phone" }),
    });
    open();

    expect(
      await screen.findByRole("heading", {
        name: "Mama Safi Laundry invited you to join as Shop staff",
      }),
    ).toBeInTheDocument();
    const phone = screen.getByLabelText("Phone number");
    expect(phone).toHaveValue("0712 345 678");
    expect(phone).toHaveAttribute("readonly");

    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByRole("heading", { name: "Enter code" })).toBeInTheDocument();
    expect(screen.getByText("We've sent a code to your phone")).toBeInTheDocument();
    expect(screen.getByText("Enter the 6-digit code sent to 0712 345 678")).toBeInTheDocument();
    // The invitation is for this number; it can't be changed here.
    expect(screen.queryByRole("button", { name: "Wrong number? Change it" })).toBeNull();
  });

  it("shows the expired message from the server", async () => {
    serveApi({
      [DETAIL]: () =>
        json(envelope("invitation_expired", "Ask Mama Safi Laundry to send a new invitation"), 410),
    });
    open();
    expect(
      await screen.findByRole("heading", {
        name: "Ask Mama Safi Laundry to send a new invitation",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send code" })).toBeNull();
  });

  it("shows X-04 for a link that doesn't exist", async () => {
    serveApi({});
    open();
    expect(
      await screen.findByRole("heading", { name: "We couldn't find that" }),
    ).toBeInTheDocument();
  });

  it("starts again at X-14 when a later step is opened directly", async () => {
    serveApi({ [DETAIL]: () => invitation() });
    open(`/invite/${TOKEN}/password`);
    expect(await screen.findByRole("button", { name: "Send code" })).toBeInTheDocument();
    expect(location()).toBe(`/invite/${TOKEN}`);
  });
});

describe("the whole journey", () => {
  function serveJourney(role = "staff", role_label = "Shop staff") {
    return serveApi({
      [DETAIL]: () => invitation(role, role_label),
      [SEND]: () => json({ message: "We've sent a code to your phone" }),
      [VERIFY]: () => json({ setup_token: "setup-1" }),
      [ACCEPT]: () => json({ access: "access-1", user: { ...ME_STAFF, role } }, 201),
      "POST /api/v1/me/pin": () => new Response(null, { status: 204 }),
      "GET /api/v1/me": () => json({ ...ME_STAFF, role }),
    });
  }

  async function throughPassword(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "Send code" }));
    await user.type(
      (await screen.findAllByRole("textbox", { name: /Digit \d of 6/ }))[0]!,
      "482916",
    );
    await user.type(await screen.findByLabelText("New password"), "kahawa-tamu");
    await user.type(screen.getByLabelText("Confirm password"), "kahawa-tamu");
    await user.click(screen.getByRole("button", { name: "Save" }));
  }

  it("staff: code, password, then a PIN entered twice, then the staff app", async () => {
    const user = userEvent.setup();
    const api = serveJourney();
    open();
    await throughPassword(user);

    expect(await screen.findByRole("heading", { name: "Choose your PIN" })).toBeInTheDocument();
    expect(getAccessToken()).toBe("access-1");
    expect(await api.to(ACCEPT)[0]?.json()).toEqual({
      setup_token: "setup-1",
      password: "kahawa-tamu",
    });

    await pressPin(user, "4826");
    expect(
      await screen.findByRole("heading", { name: "Enter your PIN again" }),
    ).toBeInTheDocument();
    await pressPin(user, "4826");

    await waitFor(() => expect(location()).toBe("/staff"));
    expect(await api.to("POST /api/v1/me/pin")[0]?.json()).toEqual({ pin: "4826" });
  });

  it("asks again when the two PINs differ", async () => {
    const user = userEvent.setup();
    const api = serveJourney();
    open();
    await throughPassword(user);
    await screen.findByRole("heading", { name: "Choose your PIN" });

    await pressPin(user, "4826");
    await pressPin(user, "4827");
    expect(
      await screen.findByText("The PINs don't match. Choose your PIN again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Choose your PIN" })).toBeInTheDocument();
    expect(api.to("POST /api/v1/me/pin")).toHaveLength(0);
  });

  it("shows the server's PIN rule and starts the PIN again", async () => {
    const user = userEvent.setup();
    const message = "That PIN is too easy to guess. Choose another.";
    serveApi({
      [DETAIL]: () => invitation(),
      [SEND]: () => json({ message: "We've sent a code to your phone" }),
      [VERIFY]: () => json({ setup_token: "setup-1" }),
      [ACCEPT]: () => json({ access: "access-1", user: ME_STAFF }, 201),
      "POST /api/v1/me/pin": () =>
        json(envelope("pin_too_common", message, { fields: { pin: [message] } }), 400),
      "GET /api/v1/me": () => json(ME_STAFF),
    });
    open();
    await throughPassword(user);
    await screen.findByRole("heading", { name: "Choose your PIN" });
    await pressPin(user, "1234");
    await pressPin(user, "1234");
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Choose your PIN" })).toBeInTheDocument();
  });

  it("accountants have no PIN and land in the console", async () => {
    const user = userEvent.setup();
    serveJourney("accountant", "Accountant");
    open();
    await throughPassword(user);
    await waitFor(() => expect(location()).toBe("/console"));
  });
});
