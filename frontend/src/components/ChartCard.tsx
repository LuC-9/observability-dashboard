import { useState, ReactNode } from "react";
import { Card, Modal, Button, Tooltip, Descriptions, Typography, Space } from "antd";
import { ExpandOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";

export interface ChartDetail {
  title: string;
  items: { label: string; value: string; copyable?: boolean }[];
  action?: { label: string; run: () => void };
}

export default function ChartCard({
  title, option, height = 300, onPick, extra,
}: {
  title: string;
  option: any;
  height?: number;
  onPick?: (params: any) => ChartDetail | null;
  extra?: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<ChartDetail | null>(null);

  const events = onPick
    ? { click: (p: any) => { const d = onPick(p); if (d) setDetail(d); } }
    : undefined;

  const chart = (h: number) => (
    <ReactECharts option={option} notMerge style={{ height: h }} onEvents={events as any} />
  );

  return (
    <Card size="small" title={title}
      extra={
        <Space size="small">
          {extra}
          <Tooltip title="Expand">
            <Button type="text" size="small" icon={<ExpandOutlined />} onClick={() => setExpanded(true)} />
          </Tooltip>
        </Space>
      }>
      {chart(height)}

      {/* full-screen view */}
      <Modal open={expanded} onCancel={() => setExpanded(false)} footer={null} width="92%" title={title} destroyOnHidden>
        {chart(Math.round((typeof window !== "undefined" ? window.innerHeight : 800) * 0.72))}
      </Modal>

      {/* click-to-detail (full ids + copy + optional drill) */}
      <Modal open={!!detail} onCancel={() => setDetail(null)} footer={null} title={detail?.title} destroyOnHidden>
        {detail && (
          <>
            <Descriptions size="small" column={1} bordered>
              {detail.items.map((it) => (
                <Descriptions.Item key={it.label} label={it.label}>
                  {it.copyable
                    ? <Typography.Text copyable={{ text: it.value }} style={{ wordBreak: "break-all" }}>{it.value}</Typography.Text>
                    : <span style={{ wordBreak: "break-all" }}>{it.value}</span>}
                </Descriptions.Item>
              ))}
            </Descriptions>
            {detail.action && (
              <Button type="primary" block style={{ marginTop: 12 }}
                onClick={() => { detail.action!.run(); setDetail(null); }}>
                {detail.action.label}
              </Button>
            )}
          </>
        )}
      </Modal>
    </Card>
  );
}
