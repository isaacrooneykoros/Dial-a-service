import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ConsoleArea from "@/apps/console/ConsoleArea";
import { setAccessToken } from "@/lib/auth";
import { envelope, json } from "@/test/fetch";
import { renderArea } from "@/test/render";
import { ME_MANAGER, ME_STAFF, serveApi, type Responder } from "@/test/server";

const LIST = "GET /api/v1/console/invitations";
const CREATE = "POST /api/v1/console/invitations";

const PENDING = {
  id: "i1",
  phone: "+254722000111",
  first_name: "Juma",
  last_name: "Otieno",
  role: "staff",
  rights: { accept_cash: true, give_discounts: false, correct_prices: false },
  branch_ids: ["b1"],
  expires_at: "2026-10-09T09:00:00Z",
  sent_count: 1,
  is_open: true,
};

function serve(extra: Record<string, Responder> = {}, pending = [PENDING]) {
  return serveApi({
    "GET /api/v1/me": () => json({ ...ME_MANAGER, role: "owner" }),
    "GET /api/v1/me/branches": () =>
      json([
        { id: "b1", name: "Kilimani" },
        { id: "b2", name: "Westlands" },
      ]),
    [LIST]: () => json({ next: null, previous: null, results: pending }),
    ...extra,
  });
}

function open() {
  return renderArea("/console", [{ path: "/console/*", element: <ConsoleArea /> }]);
}

beforeEach(() => setAccessToken("access-owner"));

describe("A-41 invite form", () => {
  it("invites a staff member with branches and rights", async () => {
    const user = userEvent.setup();
    const api = serve({
      [CREATE]: () => json({ ...PENDING, id: "i2", phone: "+254712345678" }, 201),
    });
    open();

    await user.type(await screen.findByLabelText("First name"), "Wanjiru");
    await user.type(screen.getByLabelText("Surname"), "Kamau");
    await user.type(screen.getByLabelText("Phone number"), "0712 345 678");
    expect(screen.queryByText("What they can do")).toBeNull();
    await user.click(screen.getByRole("radio", { name: "Shop staff" }));
    await user.click(await screen.findByRole("checkbox", { name: "Westlands" }));
    await user.click(screen.getByRole("checkbox", { name: "Accept cash" }));
    await user.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(await screen.findByText("Invitation sent to 0712 345 678.")).toBeInTheDocument();
    const request = api.to(CREATE)[0];
    expect(await request?.json()).toEqual({
      first_name: "Wanjiru",
      last_name: "Kamau",
      phone: "0712 345 678",
      role: "staff",
      branch_ids: ["b2"],
      rights: { accept_cash: true, give_discounts: false, correct_prices: false },
    });
    expect(request?.headers.get("Idempotency-Key")).toBeTruthy();
    expect(screen.getByLabelText("First name")).toHaveValue("");
    await waitFor(() => expect(api.to(LIST).length).toBeGreaterThan(1));
  });

  it("sends no rights for managers and accountants", async () => {
    const user = userEvent.setup();
    const api = serve({ [CREATE]: () => json(PENDING, 201) });
    open();
    await user.type(await screen.findByLabelText("First name"), "Achieng");
    await user.type(screen.getByLabelText("Surname"), "Otieno");
    await user.type(screen.getByLabelText("Phone number"), "0722000222");
    await user.click(screen.getByRole("radio", { name: "Shop staff" }));
    await user.click(screen.getByRole("checkbox", { name: "Give discounts" }));
    await user.click(screen.getByRole("radio", { name: "Shop manager" }));
    await user.click(screen.getByRole("button", { name: "Send invitation" }));
    await screen.findByText(/Invitation sent/);
    const body = (await api.to(CREATE)[0]?.json()) as { rights: unknown; role: string };
    expect(body.role).toBe("manager");
    expect(body.rights).toEqual({
      accept_cash: false,
      give_discounts: false,
      correct_prices: false,
    });
  });

  it("checks names, the number and the role before sending", async () => {
    const user = userEvent.setup();
    const api = serve();
    open();
    await user.click(await screen.findByRole("button", { name: "Send invitation" }));
    expect(await screen.findByText("Enter their first name.")).toBeInTheDocument();
    expect(screen.getByText("Enter their surname.")).toBeInTheDocument();
    expect(
      screen.getByText("Enter a Kenyan mobile number, like 0712 345 678."),
    ).toBeInTheDocument();
    expect(screen.getByText("Choose a role.")).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toHaveFocus();
    expect(api.to(CREATE)).toHaveLength(0);
  });

  it("shows the server's answer under the right field and keeps the input", async () => {
    const user = userEvent.setup();
    const message = "This number already has an account here.";
    serve({
      [CREATE]: () =>
        json(envelope("already_registered", message, { fields: { phone: [message] } }), 409),
    });
    open();
    await user.type(await screen.findByLabelText("First name"), "Wanjiru");
    await user.type(screen.getByLabelText("Surname"), "Kamau");
    await user.type(screen.getByLabelText("Phone number"), "0712345678");
    await user.click(screen.getByRole("radio", { name: "Accountant" }));
    await user.click(screen.getByRole("button", { name: "Send invitation" }));
    expect(await screen.findAllByText(message)).not.toHaveLength(0);
    expect(screen.getByLabelText("Phone number")).toHaveValue("0712345678");
    expect(screen.getByLabelText("Phone number")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("A-41 pending invitations", () => {
  it("lists them with the number, role and when the link stops working", async () => {
    serve();
    open();
    const row = (await screen.findByText("Juma Otieno")).closest("li")!;
    expect(within(row).getByText("0722 000 111 · Shop staff")).toBeInTheDocument();
    expect(within(row).getByText(/^Link works until \w{3} 9 Oct$/)).toBeInTheDocument();
  });

  it("says so when there are none", async () => {
    serve({}, []);
    open();
    expect(await screen.findByText("No pending invitations.")).toBeInTheDocument();
  });

  it("resends", async () => {
    const user = userEvent.setup();
    const api = serve({ "POST /api/v1/console/invitations/i1/resend": () => json(PENDING) });
    open();
    await user.click(await screen.findByRole("button", { name: "Resend" }));
    expect(await screen.findByText("Invitation sent again.")).toBeInTheDocument();
    expect(api.to("POST /api/v1/console/invitations/i1/resend")).toHaveLength(1);
  });

  it("cancels only after confirming", async () => {
    const user = userEvent.setup();
    const api = serve({
      "POST /api/v1/console/invitations/i1/cancel": () => json({ ...PENDING, is_open: false }),
    });
    open();
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    const dialog = screen.getByRole("alertdialog", {
      name: "Cancel the invitation for Juma Otieno?",
    });
    expect(within(dialog).getByRole("button", { name: "Keep it" })).toHaveFocus();

    await user.click(within(dialog).getByRole("button", { name: "Keep it" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(api.to("POST /api/v1/console/invitations/i1/cancel")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Cancel invitation" }));
    await waitFor(() =>
      expect(api.to("POST /api/v1/console/invitations/i1/cancel")).toHaveLength(1),
    );
  });

  it("is not shown to people who don't manage the team", async () => {
    serveApi({ "GET /api/v1/me": () => json({ ...ME_STAFF, role: "accountant" }) });
    open();
    expect(await screen.findByText("Signed in as Wanjiru K.")).toBeInTheDocument();
    expect(screen.queryByText("Invite a person")).toBeNull();
  });
});
