import { useEffect, useState } from "react";
import { Drawer, Tree, Card, Descriptions, Tag, Typography, Spin } from "antd";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { get } from "../api";
import { BRAND, ERROR_RED } from "../theme";

function buildTree(spans: any[]) {
  const byId: any = {};
  spans.forEach((s) => (byId[s.span_id] = { ...s, children: [] }));
  const roots: any[] = [];
  spans.forEach((s) => {
    if (s.parent_span_id && byId[s.parent_span_id]) byId[s.parent_span_id].children.push(byId[s.span_id]);
    else roots.push(byId[s.span_id]); // entry point = parent_span_id IS NULL
  });
  return roots;
}

const toTreeData = (nodes: any[]): any[] =>
  nodes.map((n) => ({
    key: n.span_id,
    title: (
      <span>
        <b>{n.span_name}</b>{"  "}
        <Typography.Text type="secondary">{Math.round(n.duration_ms || 0)}ms</Typography.Text>
        {n.model && <Tag color="gold" style={{ marginLeft: 6 }}>{n.model}</Tag>}
        {n.llm_cost_total_usd != null && <Tag>${Number(n.llm_cost_total_usd).toFixed(5)}</Tag>}
        {n.status_code === "ERROR" && <Tag color="red">ERROR</Tag>}
      </span>
    ),
    span: n,
    children: toTreeData(n.children),
  }));

function Waterfall({ spans }: { spans: any[] }) {
  const t0 = Math.min(...spans.map((s) => dayjs(s.start_time).valueOf()));
  const rows = spans
    .map((s) => ({ name: s.span_name, off: dayjs(s.start_time).valueOf() - t0, dur: s.duration_ms || 0, err: s.status_code === "ERROR" }))
    .sort((a, b) => a.off - b.off);
  const opt = {
    grid: { left: 170, right: 20, top: 10, bottom: 30 },
    xAxis: { type: "value", name: "ms" },
    yAxis: { type: "category", data: rows.map((r) => r.name), inverse: true, axisLabel: { width: 160, overflow: "truncate" } },
    tooltip: { trigger: "axis" },
    series: [
      { type: "bar", stack: "w", itemStyle: { color: "transparent" }, data: rows.map((r) => r.off) },
      { type: "bar", stack: "w", data: rows.map((r) => ({ value: r.dur || 0.5, itemStyle: { color: r.err ? ERROR_RED : BRAND.gold } })) },
    ],
  };
  return <ReactECharts option={opt} style={{ height: Math.max(160, rows.length * 26) }} />;
}

export default function TraceDrawer({ traceId, open, onClose }: { traceId: string | null; open: boolean; onClose: () => void }) {
  const [spans, setSpans] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !traceId) return;
    setLoading(true); setSel(null); setSpans([]);
    get(`/traces/${traceId}`).then((s) => { setSpans(s); setSel(s.find((x: any) => !x.parent_span_id) || s[0]); })
      .finally(() => setLoading(false));
  }, [open, traceId]);

  return (
    <Drawer width={920} open={open} onClose={onClose} title={`Trace · ${traceId || ""}`}>
      <Spin spinning={loading}>
        <Card size="small" title="Span tree (entry point = root span)" style={{ marginBottom: 12 }}>
          <Tree defaultExpandAll treeData={toTreeData(buildTree(spans))}
            onSelect={(_, info: any) => setSel(info.node.span)} />
        </Card>
        <Card size="small" title="Waterfall" style={{ marginBottom: 12 }}>
          {spans.length > 0 && <Waterfall spans={spans} />}
        </Card>
        {sel && (
          <Card size="small" title={`Span · ${sel.span_name}`}>
            <Descriptions size="small" column={2} bordered>
              <Descriptions.Item label="Service">{sel.service_name}</Descriptions.Item>
              <Descriptions.Item label="Agent">{sel.agent_name || "—"}</Descriptions.Item>
              <Descriptions.Item label="Model">{sel.model || "—"}</Descriptions.Item>
              <Descriptions.Item label="Status">{sel.status_code}</Descriptions.Item>
              <Descriptions.Item label="Duration">{Math.round(sel.duration_ms || 0)} ms</Descriptions.Item>
              <Descriptions.Item label="Cost">{sel.llm_cost_total_usd != null ? `$${Number(sel.llm_cost_total_usd).toFixed(6)}` : "—"}</Descriptions.Item>
              <Descriptions.Item label="In tokens">{sel.gen_ai_input_tokens ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="Out tokens">{sel.gen_ai_output_tokens ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="Input" span={2}>{sel.input_text || "—"}</Descriptions.Item>
              <Descriptions.Item label="Output" span={2}>{sel.output_text || "—"}</Descriptions.Item>
            </Descriptions>
          </Card>
        )}
      </Spin>
    </Drawer>
  );
}
