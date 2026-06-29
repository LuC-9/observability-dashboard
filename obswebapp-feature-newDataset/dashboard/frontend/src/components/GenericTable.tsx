import { Table, Button, Space } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { fmtTime } from "../timeUtil";

const isTs = (v: any) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v);
const titleize = (k: string) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function cell(v: any) {
  if (v === null || v === undefined) return "—";
  if (isTs(v)) return fmtTime(v);
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(6);
  const s = String(v);
  return s.length > 120 ? s.slice(0, 120) + "…" : s;
}

function toCSV(rows: any[]) {
  if (!rows.length) return "";
  const keys = Object.keys(rows[0]);
  const esc = (x: any) => `"${String(x ?? "").replace(/"/g, '""')}"`;
  return [keys.join(","), ...rows.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
}

export default function GenericTable({
  rows, loading, onRowClick, exportName = "export",
  total, page, pageSize, onPageChange,
}: {
  rows: any[]; loading?: boolean; onRowClick?: (r: any) => void; exportName?: string;
  total?: number; page?: number; pageSize?: number; onPageChange?: (p: number, ps: number) => void;
}) {
  const server = total !== undefined;
  const keys = rows.length ? Object.keys(rows[0]) : [];
  const columns = keys.map((k) => ({
    title: titleize(k),
    dataIndex: k,
    key: k,
    ellipsis: true,
    sorter: (a: any, b: any) =>
      typeof a[k] === "number" ? a[k] - b[k] : String(a[k] ?? "").localeCompare(String(b[k] ?? "")),
    render: cell,
  }));

  const download = () => {
    const blob = new Blob([toCSV(rows)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${exportName}.csv`;
    a.click();
  };

  return (
    <>
      <Space style={{ marginBottom: 8 }}>
        <Button size="small" icon={<DownloadOutlined />} onClick={download} disabled={!rows.length}>
          Export CSV
        </Button>
        <span style={{ color: "#999" }}>{rows.length} rows</span>
      </Space>
      <Table
        size="small"
        loading={loading}
        dataSource={rows.map((r, i) => ({ key: i, ...r }))}
        columns={columns}
        scroll={{ x: "max-content" }}
        pagination={
          server
            ? { current: page, pageSize, total, showSizeChanger: true,
                showTotal: (t) => `${t} total`,
                onChange: (p, ps) => onPageChange?.(p, ps) }
            : { pageSize: 25, showSizeChanger: true }
        }
        onRow={(r) => ({ onClick: () => onRowClick?.(r), style: { cursor: onRowClick ? "pointer" : "default" } })}
      />
    </>
  );
}
