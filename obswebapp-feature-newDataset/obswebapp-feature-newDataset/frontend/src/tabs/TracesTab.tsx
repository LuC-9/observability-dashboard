import { useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import WaterfallModal from "../components/WaterfallModal";
import Spinner from "../components/Spinner";
import { SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { FilterOptions, SharedFilters, TracesResponse } from "../types";

const TRACE_LIST_COLS = [
  "trace_id", "trace_start", "total_duration_ms", "span_count",
  "error_count", "service_name", "agents",
];

export default function TracesTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [agent, setAgent]   = useState("All");
  const [status, setStatus] = useState("All");
  const [limit, setLimit]   = useState(100);
  const [appliedLimit, setAppliedLimit] = useState(100);

  const [data, setData]       = useState<TracesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");

  const [modalTraceId, setModalTraceId] = useState<string | null>(null);

  const agents = ["All", ...options.agents];

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.traces({ ...filters, agent, status, limit: appliedLimit }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, agent, status, appliedLimit]);

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Agent</label>
          <select className="field-select" value={agent} onChange={(e) => setAgent(e.target.value)}>
            {agents.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Status Code</label>
          <select className="field-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {["All", "UNSET", "OK", "ERROR"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ flex: 2, minWidth: 220 }}>
          <label className="field-label">Trace Limit: {limit}</label>
          <input type="range" min={50} max={500} step={50} value={limit}
                 onChange={(e) => setLimit(Number(e.target.value))}
                 onPointerUp={(e) => setAppliedLimit(Number((e.target as HTMLInputElement).value))} />
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      <div className="section-h">Trace List — click a row to open waterfall</div>
      {data === null && loading
        ? <SkeletonTable />
        : <DataTable
            columns={TRACE_LIST_COLS}
            rows={data?.trace_list ?? []}
            onRowClick={(row) => setModalTraceId(String(row.trace_id ?? ""))}
            emptyText="No traces found"
            pageSize={25}
          />
      }

      {data && (
        <details className="accordion">
          <summary>Analytics Charts</summary>
          <div className="accordion-body">
            <div className="responsive-grid">
              <PlotlyChart fig={data.charts.latency_hist} />
              <PlotlyChart fig={data.charts.by_agent} />
              <PlotlyChart fig={data.charts.cost} />
              <PlotlyChart fig={data.charts.tokens} />
            </div>
          </div>
        </details>
      )}

      {modalTraceId && (
        <WaterfallModal traceId={modalTraceId} onClose={() => setModalTraceId(null)} />
      )}
    </div>
  );
}
