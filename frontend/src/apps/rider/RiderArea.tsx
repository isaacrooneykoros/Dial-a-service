import { PlaceholderArea } from "@/apps/PlaceholderArea";

/** The rider route area. Loaded only when opened, so other areas never download it. */
export default function RiderArea() {
  return <PlaceholderArea area="rider" />;
}
