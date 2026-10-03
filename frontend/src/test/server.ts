// A fake API for screen tests: answers by "METHOD /path", 404 for anything else.
import { envelope, json, mockFetch, pathOf } from "@/test/fetch";

export type Responder = (request: Request) => Response | Promise<Response>;

export function serveApi(routes: Record<string, Responder>) {
  const mock = mockFetch((request) => {
    const responder = routes[`${request.method} ${pathOf(request)}`];
    return responder
      ? responder(request)
      : json(envelope("not_found", "We couldn't find that"), 404);
  });
  return {
    ...mock,
    /** Requests to `METHOD /path`, as unread copies. */
    to: (route: string) => mock.requests.filter((r) => `${r.method} ${pathOf(r)}` === route),
  };
}

export const ME_STAFF = {
  id: "7d3c1d64-8a52-4e63-9d0c-0d7c1c5b8a11",
  phone: "+254712345678",
  first_name: "Wanjiru",
  last_name: "Kamau",
  role: "staff",
  language: "en",
  is_phone_verified: true,
  rights: { accept_cash: false, give_discounts: false, correct_prices: false },
  has_pin: false,
};

export const ME_MANAGER = {
  ...ME_STAFF,
  id: "9b1e7f20-3c4d-4e5f-8a9b-0c1d2e3f4a5b",
  first_name: "Achieng",
  last_name: "Otieno",
  role: "manager",
  has_pin: true,
};
