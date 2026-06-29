import { useState } from "react";
import Plot from "react-plotly.js";
import type { PlotlyFig } from "../types";
import ChartModal from "./ChartModal";

interface Props {
  fig: PlotlyFig;
  height?: number;
}

const lightThemeLayout = {
  template: 'plotly_white',
  font: {
    color: '#1f2937', // slate-800
    family: "Inter, sans-serif"
  },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  legend: {
    bgcolor: '#ffffff',
    bordercolor: '#e2e8f0',
    borderwidth: 1,
    font: {
      color: '#1f2937'
    }
  }
};

export default function PlotlyChart({ fig, height }: Props) {
  const [open, setOpen] = useState(false);
  const layout = {
    ...fig.layout,
    ...lightThemeLayout,
    legend: fig.layout?.legend ? {
      ...lightThemeLayout.legend,
      ...fig.layout.legend,
      bgcolor: '#ffffff',
      bordercolor: '#e2e8f0',
      font: {
        ...lightThemeLayout.legend.font,
        ...fig.layout.legend.font,
        color: '#1f2937'
      }
    } : lightThemeLayout.legend,
    ...(height ? { height } : {})
  };

  return (
    <>
      <div
        onClick={() => setOpen(true)}
        title="Click to expand"
        style={{ cursor: "zoom-in", position: "relative", width: "100%", overflow: "hidden" }}
      >
        <Plot
          data={fig.data}
          layout={{ ...layout, autosize: true }}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          style={{ width: "100%", height: layout?.height ? `${layout.height}px` : "auto", pointerEvents: "none" }}
        />
      </div>

      {open && <ChartModal fig={{...fig, layout}} onClose={() => setOpen(false)} />}
    </>
  );
}
