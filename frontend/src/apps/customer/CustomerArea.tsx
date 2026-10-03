import { PlaceholderArea } from "@/apps/PlaceholderArea";

/** The customer route area. Loaded only when opened, so other areas never download it. */
export default function CustomerArea() {
  return <PlaceholderArea area="customer" />;
}
