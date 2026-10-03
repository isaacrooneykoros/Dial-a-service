import { InviteRoutes } from "@/apps/shared/invite/InviteRoutes";

/** /invite/:token, the invitation link (X-14). Its own chunk, loaded only from the SMS link. */
export default function InviteArea() {
  return <InviteRoutes />;
}
