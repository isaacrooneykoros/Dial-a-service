import { PlaceholderArea } from "@/apps/PlaceholderArea";
import { SignInRoutes } from "@/apps/shared/signin/SignInRoutes";

/** The console route area. Loaded only when opened, so other areas never download it. */
export default function ConsoleArea() {
  return <SignInRoutes app="console" signedIn={<PlaceholderArea area="console" />} />;
}
