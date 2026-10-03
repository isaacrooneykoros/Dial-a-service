// Skeletons shaped like the content they stand in for (10-screens-shared.md,
// "First load"). Hidden from screen readers; FirstLoad announces loading instead.
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`animate-pulse rounded-control bg-border motion-reduce:animate-none ${className}`}
    />
  );
}

/** A list row: a title line and a shorter detail line. */
export function SkeletonRow() {
  return (
    <div aria-hidden className="flex flex-col gap-2 border-b border-border py-3">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  );
}
