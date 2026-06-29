import type { SharedFilters } from "../types";

interface Props {
  value: SharedFilters;
  onChange: (next: SharedFilters) => void;
  quickRanges: string[];
  services: string[];
  onRefresh: () => void;
  refreshing?: boolean;
}

export default function FilterBar({ value, onChange, quickRanges, services, onRefresh, refreshing }: Props) {
  const set = (patch: Partial<SharedFilters>) => onChange({ ...value, ...patch });

  const isCustom = value.quick === "Custom";

  return (
    <div className="filter-bar">
      <div style={{ flex: 2, minWidth: 160 }}>
        <label className="field-label">Quick Range</label>
        <select className="field-select" value={value.quick} onChange={(e) => set({ quick: e.target.value })}>
          {quickRanges.map((q) => <option key={q} value={q}>{q}</option>)}
        </select>
      </div>

      <div style={{ flex: 2, minWidth: 160 }}>
        <label className="field-label">Service</label>
        <select className="field-select" value={value.service} onChange={(e) => set({ service: e.target.value })}>
          <option value="All">All Services</option>
          {services.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {isCustom && (
        <>
          <div style={{ flex: 2, minWidth: 160 }}>
            <label className="field-label">Start Date (YYYY-MM-DD)</label>
            <input className="field-input" value={value.start} onChange={(e) => set({ start: e.target.value })} />
          </div>
          <div style={{ flex: 2, minWidth: 160 }}>
            <label className="field-label">End Date (YYYY-MM-DD)</label>
            <input className="field-input" value={value.end} onChange={(e) => set({ end: e.target.value })} />
          </div>
        </>
      )}

      <button className="btn-primary" onClick={onRefresh} disabled={refreshing} style={{ height: 35 }}>
        {refreshing ? "Refreshing…" : "Refresh Filters"}
      </button>
    </div>
  );
}
