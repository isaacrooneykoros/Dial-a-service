import { PlaceholderArea } from "@/apps/PlaceholderArea";

/** The public route area. Loaded only when opened, so other areas never download it. */
export default function PublicArea() {
  return <PlaceholderArea area="public" />;
}
