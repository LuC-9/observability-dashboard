import { useState } from "react";
import { Drawer, Form, InputNumber, Select, Button, Divider, Typography } from "antd";
import { useThemeCtx, FONT_OPTIONS } from "../ThemeProvider";
import { TZ_OPTIONS, setZone, getZone } from "../timeUtil";
import PricingManager from "./PricingManager";

export interface Settings {
  budgetCost: number;
  budgetErr: number;
  autoSeconds: number;
  defaultRange: string;
  pageSize: number;
}

const RANGES = ["5m", "10m", "30m", "1h", "6h", "12h", "1d"].map((v) => ({ value: v, label: v }));

export default function SettingsDrawer({
  open, onClose, settings, onSave,
}: { open: boolean; onClose: () => void; settings: Settings; onSave: (s: Settings) => void }) {
  const [form] = Form.useForm();
  const { font, setFont } = useThemeCtx();
  const [pricingOpen, setPricingOpen] = useState(false);

  const onFinish = (v: any) => {
    setFont(v.font);          // apply font app-wide
    setZone(v.tz);            // apply timezone for all timestamps
    onSave({                  // persist the rest + trigger a re-render
      budgetCost: Number(v.budgetCost), budgetErr: Number(v.budgetErr),
      autoSeconds: Number(v.autoSeconds), defaultRange: v.defaultRange, pageSize: Number(v.pageSize),
    });
    onClose();
  };

  return (
    <Drawer title="Settings" open={open} onClose={onClose} width={380}>
      <Form layout="vertical" form={form} onFinish={onFinish}
        initialValues={{ ...settings, font, tz: getZone() }}>
        <Typography.Title level={5}>Appearance</Typography.Title>
        <Form.Item name="font" label="Font (applies everywhere)">
          <Select options={FONT_OPTIONS.map((f) => ({ value: f, label: f }))} />
        </Form.Item>
        <Form.Item name="tz" label="Timezone (all timestamps)">
          <Select options={TZ_OPTIONS} showSearch />
        </Form.Item>

        <Divider />
        <Typography.Title level={5}>Budget &amp; alerts</Typography.Title>
        <Form.Item name="budgetCost" label="Cost budget (USD per selected window)"
          tooltip="Red banner appears when the window's cost exceeds this. 0 = off.">
          <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="budgetErr" label="Error-rate alert (%)" tooltip="0 = off.">
          <InputNumber min={0} max={100} style={{ width: "100%" }} />
        </Form.Item>

        <Divider />
        <Typography.Title level={5}>Refresh &amp; tables</Typography.Title>
        <Form.Item name="autoSeconds" label="Auto-refresh interval (seconds)">
          <InputNumber min={15} step={15} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="defaultRange" label="Default time range">
          <Select options={RANGES} />
        </Form.Item>
        <Form.Item name="pageSize" label="Table page size">
          <InputNumber min={10} step={10} max={500} style={{ width: "100%" }} />
        </Form.Item>

        <Button type="primary" htmlType="submit" block>Save</Button>
      </Form>

      <Divider />
      <Typography.Title level={5}>Data / config</Typography.Title>
      <Button block onClick={() => setPricingOpen(true)}>Manage LLM pricing</Button>
      <PricingManager open={pricingOpen} onClose={() => setPricingOpen(false)} />
    </Drawer>
  );
}
