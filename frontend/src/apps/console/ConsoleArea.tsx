import { PlaceholderArea } from "@/apps/PlaceholderArea";

/** The console route area. Loaded only when opened, so other areas never download it. */
export default function ConsoleArea() {
  return <PlaceholderArea area="console" />;
}
