export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  className?: string;
}

/** Single shimmering block. */
export function Skeleton({ width, height = 12, radius, className }: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className ?? ""}`}
      style={{
        width: width ?? "100%",
        height,
        borderRadius: radius,
      }}
      aria-hidden="true"
    />
  );
}

/** Multi-line text skeleton. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="skeleton skeleton-line"
          style={{ width: index === lines - 1 ? "70%" : "100%" }}
        />
      ))}
    </div>
  );
}

/** Card-shaped skeleton used while lists load. */
export function SkeletonCard() {
  return (
    <div className="card card-pad" aria-hidden="true">
      <Skeleton width="45%" height={18} radius={8} />
      <div style={{ height: 14 }} />
      <SkeletonText lines={3} />
    </div>
  );
}
