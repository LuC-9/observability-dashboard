import { useEffect } from "react";
import Plot from "react-plotly.js";
import type { PlotlyFig } from "../types";

interface Props {
  fig: PlotlyFig;
  onClose: () => void;
}

export default function ChartModal({ fig, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.75)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 12,
          padding: 16,
          width: "90vw",
          maxWidth: 1400,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <button
            onClick={onClose}
            style={{
              background: "transparent", border: "1px solid #e5e7eb",
              borderRadius: 6, color: "#6b7280", cursor: "pointer",
              fontSize: 18, lineHeight: 1, padding: "2px 10px",
            }}
          >
            ✕
          </button>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <Plot
            data={fig.data}
            layout={{ ...fig.layout, autosize: true, height: undefined }}
            config={{ displayModeBar: true, responsive: true }}
            useResizeHandler
            style={{ width: "100%", height: "75vh" }}
          />
        </div>
      </div>
    </div>
  );
}
