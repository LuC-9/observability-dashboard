import { useEffect, useState } from "react";
import { Table, Tag, Typography, Alert } from "antd";
import dayjs from "dayjs";
import { get } from "../api";

const fmtAgo = (mins: number) => {
  if (mins == null) return "—";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
};

export default function Health({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    get("/health").then(setRows).finally(() => setLoading(false));
  }, [refreshKey]);

  const status = (m: number) =>
    m == null ? <Tag>unknown</Tag>
      : m <= 30 ? <Tag color="green">live</Tag>
      : m <= 180 ? <Tag color="gold">quiet</Tag>
      : <Tag color="red">stale</Tag>;

  const columns = [
    { title: "Service", dataIndex: "service_name", sorter: (a: any, b: any) => String(a.service_name).localeCompare(b.service_name) },
    { title: "Platform", dataIndex: "platform" },
    { title: "Project", dataIndex: "project_id" },
    { title: "Status", dataIndex: "minutes_since", render: (m: number) => status(m),
      sorter: (a: any, b: any) => (a.minutes_since || 0) - (b.minutes_since || 0) },
    { title: "Last seen", dataIndex: "minutes_since", render: (m: number) => fmtAgo(m) },
    { title: "Last ts", dataIndex: "last_seen", render: (t: string) => (t ? dayjs(t).format("MMM D HH:mm:ss") : "—") },
    { title: "Traces (48h)", dataIndex: "traces_48h", sorter: (a: any, b: any) => (a.traces_48h || 0) - (b.traces_48h || 0) },
    { title: "Cost (48h)", dataIndex: "cost_48h", render: (v: number) => (v != null ? `$${Number(v).toFixed(4)}` : "—") },
    { title: "Error rate", dataIndex: "error_rate", render: (v: number) => `${((v || 0) * 100).toFixed(1)}%`,
      sorter: (a: any, b: any) => (a.error_rate || 0) - (b.error_rate || 0) },
  ];

  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }}
        message="Service health (last 48h, all services)"
        description="Independent of the page time filter. live ≤30m · quiet ≤3h · stale >3h since last span — spot services that stopped emitting." />
      <Typography.Text type="secondary">{rows.length} services</Typography.Text>
      <Table size="small" loading={loading} rowKey="service_name" style={{ marginTop: 8 }}
        dataSource={rows} columns={columns as any} pagination={{ pageSize: 25 }} />
    </>
  );
}
