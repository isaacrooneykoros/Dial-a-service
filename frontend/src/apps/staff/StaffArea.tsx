import { PlaceholderArea } from "@/apps/PlaceholderArea";
import { SignInRoutes } from "@/apps/shared/signin/SignInRoutes";

/** The staff route area. Loaded only when opened, so other areas never download it. */
export default function StaffArea() {
  return <SignInRoutes app="staff" signedIn={<PlaceholderArea area="staff" />} />;
}
