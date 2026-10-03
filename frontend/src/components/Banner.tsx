// Banner (10-screens-shared.md, components): info, warning, error, offline.
// Every tone has an icon as well as a colour, so it reads without colour.
import { CircleAlert, Info, TriangleAlert, WifiOff, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type BannerTone = "info" | "warning" | "error" | "offline";

const TONES: Record<BannerTone, { icon: LucideIcon; className: string }> = {
  info: { icon: Info, className: "border-info text-info" },
  warning: { icon: TriangleAlert, className: "border-warning text-warning" },
  error: { icon: CircleAlert, className: "border-danger text-danger" },
  offline: { icon: WifiOff, className: "border-text-muted text-text-muted" },
};

export interface BannerProps {
  tone: BannerTone;
  children: ReactNode;
  /** A button, such as Retry. */
  action?: ReactNode;
  className?: string;
}

export function Banner({ tone, children, action, className = "" }: BannerProps) {
  const { icon: Icon, className: toneClass } = TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-start gap-3 rounded-card border bg-surface p-3 ${toneClass} ${className}`}
    >
      <Icon aria-hidden size={24} strokeWidth={1.75} className="shrink-0" />
      <div className="min-w-0 flex-1 text-secondary text-text">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
