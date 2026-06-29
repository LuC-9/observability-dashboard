function SkeletonBlock({ height, borderRadius = 8 }: { height: number; borderRadius?: number }) {
  return <div className="skeleton" style={{ height, borderRadius }} />;
}

export function SkeletonCharts({ cols = 2, rows = 2, height = 320 }: { cols?: number; rows?: number; height?: number }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 12, marginBottom: 16 }}>
      {Array.from({ length: cols * rows }).map((_, i) => (
        <SkeletonBlock key={i} height={height} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 8 }: { rows?: number }) {
  return (
    <div className="table-wrap" style={{ padding: "14px 16px" }}>
      <SkeletonBlock height={28} borderRadius={4} />
      <div style={{ marginTop: 8 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} style={{ marginTop: 6 }}>
            <SkeletonBlock height={24} borderRadius={4} />
          </div>
        ))}
      </div>
    </div>
  );
}
