// Empty state (10-screens-shared.md): an icon, one short sentence and one action.
// No illustrations in the MVP.
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon: LucideIcon;
  message: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-4 px-4 py-12 text-center">
      <Icon aria-hidden size={24} strokeWidth={1.75} className="text-text-muted" />
      <p className="text-body text-text-muted">{message}</p>
      {action}
    </div>
  );
}
