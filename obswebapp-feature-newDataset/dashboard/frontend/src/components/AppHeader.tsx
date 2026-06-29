import { useState } from "react";
import { Layout, Button, Typography, Space, Tooltip, Switch, Tag } from "antd";
import { ReloadOutlined, ThunderboltOutlined, LogoutOutlined, SettingOutlined, SearchOutlined } from "@ant-design/icons";
import { BRAND } from "../theme";
import { fmtTime } from "../timeUtil";
import { useAuth } from "../auth";

function Logo() {
  const [ok, setOk] = useState(true);
  return ok ? (
    <img src="/branding/logo.png" alt="L'Oréal" style={{ height: 34 }} onError={() => setOk(false)} />
  ) : (
    <Typography.Text strong style={{ color: "#fff", fontSize: 16, letterSpacing: 1 }}>
      L'ORÉAL <span style={{ color: BRAND.gold }}>· GenAI Observability</span>
    </Typography.Text>
  );
}

export default function AppHeader({
  lastRefresh, onRefetch, onRunPipeline, busy, autoRefresh, setAutoRefresh,
  pipelineRunning, onOpenSettings, onOpenSearch,
}: {
  lastRefresh: Record<string, string | null>;
  onRefetch: () => void;
  onRunPipeline: () => void;
  busy: boolean;
  autoRefresh: boolean;
  setAutoRefresh: (b: boolean) => void;
  pipelineRunning: boolean;
  onOpenSettings: () => void;
  onOpenSearch: () => void;
}) {
  const { logout, user } = useAuth();
  const newest = Object.values(lastRefresh).filter(Boolean).sort().slice(-1)[0];
  const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);
  const kbd = isMac ? "⌘K" : "Ctrl+K";

  return (
    <Layout.Header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingInline: 20 }}>
      <Logo />
      <Space size="middle">
        <Tooltip title="Find anything — traces, services, sessions, models. Your keyboard's favourite combo.">
          <Button onClick={onOpenSearch} icon={<SearchOutlined />}
            style={{ background: "#1f1f1f", borderColor: "#333", color: "#bbb" }}>
            Search <Tag style={{ marginLeft: 6, marginRight: 0, background: "#000", color: "#999", border: "1px solid #333" }}>{kbd}</Tag>
          </Button>
        </Tooltip>
        <Tooltip title={`Gold freshness — spans: ${lastRefresh.spans || "—"} · logs: ${lastRefresh.logs || "—"} · metrics: ${lastRefresh.metrics || "—"}. Older than your coffee? Hit Run pipeline.`}>
          <Tag color="gold" style={{ marginInlineEnd: 0 }}>
            Last data: {newest ? fmtTime(newest) : "—"}
          </Tag>
        </Tooltip>
        <Tooltip title="Auto-refresh: set it and forget it.">
          <Space size={4}>
            <Typography.Text style={{ color: "#aaa" }}>Auto</Typography.Text>
            <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} />
          </Space>
        </Tooltip>
        <Tooltip title="Re-read the gold tables. Instant and painless — no goblins were harmed.">
          <Button icon={<ReloadOutlined />} onClick={onRefetch} loading={busy}>Refresh</Button>
        </Tooltip>
        <Tooltip title={pipelineRunning
          ? "The data goblins are hard at work. Patience, friend…"
          : "Summons the whole pull + merge pipeline (~a few minutes, real compute). It already runs every 10 min — don't summon the goblins for fun."}>
          <Button onClick={onRunPipeline} disabled={pipelineRunning}
            icon={<ThunderboltOutlined className={pipelineRunning ? "pulsing" : ""} style={{ color: pipelineRunning ? BRAND.gold : undefined }} />}>
            {pipelineRunning ? "Running…" : "Run pipeline"}
          </Button>
        </Tooltip>
        <Tooltip title="Knobs, dials, fonts & timezones.">
          <Button type="text" icon={<SettingOutlined style={{ color: "#fff" }} />} onClick={onOpenSettings} />
        </Tooltip>
        <Typography.Text style={{ color: "#888" }}>{user}</Typography.Text>
        <Tooltip title="Escape hatch.">
          <Button type="text" icon={<LogoutOutlined style={{ color: "#fff" }} />} onClick={logout} />
        </Tooltip>
      </Space>
    </Layout.Header>
  );
}
