import { useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import SessionDetailModal from "../components/SessionDetailModal";
import Spinner from "../components/Spinner";
import { SkeletonCharts, SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { FilterOptions, SessionsResponse, SharedFilters } from "../types";

const SESSION_COLS = [
  "session_id", "agent_id", "start_time", "end_time",
  "total_turns", "status", "total_cost",
];

export default function SessionsTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [agent, setAgent]   = useState("All");
  const [status, setStatus] = useState("All");

  const [data, setData]       = useState<SessionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");

  const [modalSessionId, setModalSessionId] = useState<string | null>(null);

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.sessions({ ...filters, agent, status }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, agent, status]);

  const agents = ["All", ...(options.agents ?? [])];

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
          <label className="field-label">Status</label>
          <select className="field-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {["All", "completed", "failed"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data === null && loading
        ? <SkeletonCharts />
        : data && (
            <div className="responsive-grid" style={{ marginBottom: 16 }}>
              <PlotlyChart fig={data.charts.status_pie} />
              <div className="sessions-over-time-chart">
                <PlotlyChart fig={data.charts.sessions_over_time} />
              </div>
              <PlotlyChart fig={data.charts.cost_by_agent} />
              <PlotlyChart fig={data.charts.turns_hist} />
            </div>
          )
      }

      <div className="section-h">Sessions — click a row to view details</div>
      {data === null && loading
        ? <SkeletonTable />
        : <DataTable
            columns={SESSION_COLS}
            rows={data?.sessions ?? []}
            onRowClick={(row) => setModalSessionId(String(row.session_id ?? ""))}
            emptyText="No sessions found"
            pageSize={25}
            truncateColumns={["session_id"]}
          />
      }

      {modalSessionId && (
        <SessionDetailModal sessionId={modalSessionId} onClose={() => setModalSessionId(null)} />
      )}
    </div>
  );
}
