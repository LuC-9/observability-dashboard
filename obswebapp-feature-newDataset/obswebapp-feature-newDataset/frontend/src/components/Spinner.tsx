export default function Spinner({ size = 20, color = "#3b82f6" }: { size?: number; color?: string }) {
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: "50%",
      border: `${Math.max(2, size / 10)}px solid #e5e7eb`,
      borderTopColor: color,
      animation: "spin 0.65s linear infinite",
      flexShrink: 0,
    }} />
  );
}
