import { PlaceholderArea } from "@/apps/PlaceholderArea";

/** The staff route area. Loaded only when opened, so other areas never download it. */
export default function StaffArea() {
  return <PlaceholderArea area="staff" />;
}
