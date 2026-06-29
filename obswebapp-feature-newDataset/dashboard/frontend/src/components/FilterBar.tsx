import { useEffect, useState } from "react";
import { Select, Space, DatePicker, Card } from "antd";
import { get, Scope } from "../api";

const RANGES = [
  { value: "5m", label: "Last 5 min" }, { value: "10m", label: "Last 10 min" },
  { value: "30m", label: "Last 30 min" }, { value: "1h", label: "Last 1 hour" },
  { value: "6h", label: "Last 6 hours" }, { value: "12h", label: "Last 12 hours" },
  { value: "1d", label: "Last 1 day" }, { value: "custom", label: "Custom range" },
];

const opts = (rows: any[], key: string) => rows.map((r) => ({ value: r[key], label: r[key] }));
const toArr = (s?: string) => (s ? s.split(",").filter(Boolean) : []);
const fromArr = (a: string[]) => (a.length ? a.join(",") : undefined);

export default function FilterBar({ scope, onChange }: { scope: Scope; onChange: (s: Scope) => void }) {
  const [projects, setProjects] = useState<any[]>([]);
  const [platforms, setPlatforms] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  useEffect(() => { get("/filters/projects").then(setProjects); }, []);
  useEffect(() => { get("/filters/platforms", { project: scope.project }).then(setPlatforms); }, [scope.project]);
  // services depend on project only (platform is now multi-select)
  useEffect(() => { get("/filters/services", { project: scope.project }).then(setServices); }, [scope.project]);

  const set = (patch: Partial<Scope>) => onChange({ ...scope, ...patch });

  return (
    <Card size="small" style={{ marginBottom: 12 }} styles={{ body: { padding: 12 } }}>
      <Space wrap size="middle">
        <Select allowClear showSearch placeholder="Project" style={{ width: 240 }} value={scope.project}
          options={opts(projects, "project_id")}
          onChange={(v) => set({ project: v, platform: undefined, service: undefined })} />
        <Select mode="multiple" allowClear placeholder="GCP service (platform)" style={{ minWidth: 220, maxWidth: 360 }}
          value={toArr(scope.platform)} maxTagCount="responsive"
          options={opts(platforms, "source_platform")}
          onChange={(v) => set({ platform: fromArr(v) })} />
        <Select mode="multiple" allowClear showSearch placeholder="Service name" style={{ minWidth: 220, maxWidth: 360 }}
          value={toArr(scope.service)} maxTagCount="responsive"
          options={opts(services, "service_name")}
          onChange={(v) => set({ service: fromArr(v) })} />
        <Select style={{ width: 160 }} value={scope.time_range || "1h"} options={RANGES}
          onChange={(v) => set({ time_range: v })} />
        {scope.time_range === "custom" && (
          <DatePicker.RangePicker showTime
            onChange={(d) => set({ start: d?.[0]?.toISOString(), end: d?.[1]?.toISOString() })} />
        )}
      </Space>
    </Card>
  );
}
