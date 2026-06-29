import { useEffect, useState } from "react";
import { Modal, Table, Form, Input, InputNumber, Switch, Button, Space, Typography, App } from "antd";
import { get, api } from "../api";
import { fmtTime } from "../timeUtil";

export default function PricingManager({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message, modal } = App.useApp();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const load = () => { setLoading(true); get("/config/pricing").then(setRows).finally(() => setLoading(false)); };
  useEffect(() => { if (open) load(); }, [open]);

  const toggleActive = async (id: string, active: boolean) => {
    try { await api.patch(`/config/pricing/${id}`, { active }); load(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "update failed"); }
  };

  const doSave = async (v: any, force: boolean) => {
    await api.post("/config/pricing", {
      model_prefix: v.model_prefix.trim(),
      input_cost: Number(v.input_cost),
      output_cost: Number(v.output_cost),
      active: !!v.active,
      force,
    });
  };

  const onSave = (v: any) => {
    const name = (v.model_prefix || "").trim();
    if (!name) { message.error("Model name is required"); return; }
    modal.confirm({
      title: "Save this pricing?",
      content: `${name} — input $${v.input_cost}/1M, output $${v.output_cost}/1M, active: ${v.active ? "yes" : "no"}`,
      okText: "Save", cancelText: "Cancel",
      onOk: async () => {
        try {
          await doSave({ ...v, model_prefix: name }, false);
          message.success("Pricing saved"); form.resetFields(); form.setFieldsValue({ active: true }); load();
        } catch (e: any) {
          if (e?.response?.status === 409) {
            modal.confirm({
              title: "Active price already exists",
              content: `An active price for "${name}" exists. Deactivate the old one and add this new one (SCD2)?`,
              okText: "Deactivate old & add new", okButtonProps: { danger: true }, cancelText: "Cancel",
              onOk: async () => {
                try { await doSave({ ...v, model_prefix: name }, true); message.success("Previous deactivated; new price added"); form.resetFields(); form.setFieldsValue({ active: true }); load(); }
                catch (er: any) { message.error(er?.response?.data?.detail || "save failed"); }
              },
            });
          } else message.error(e?.response?.data?.detail || "save failed");
        }
      },
    });
  };

  const columns = [
    { title: "Model prefix", dataIndex: "model_prefix" },
    { title: "Input $/1M", dataIndex: "input_cost", render: (v: any) => Number(v).toFixed(4) },
    { title: "Output $/1M", dataIndex: "output_cost", render: (v: any) => Number(v).toFixed(4) },
    { title: "Active", dataIndex: "active",
      render: (a: boolean, r: any) => <Switch checked={a} onChange={(v) => toggleActive(r.id, v)} /> },
    { title: "Updated", dataIndex: "updated_at", render: (t: any) => fmtTime(t) },
  ];

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={820} title="LLM pricing (config_ds.llm_pricing)" destroyOnHidden>
      <Typography.Paragraph type="secondary">
        Only <b>active</b> rows are used for cost. To change a price, add a new one — you'll be asked to deactivate the old (SCD2).
      </Typography.Paragraph>

      <Table size="small" rowKey="id" loading={loading} dataSource={rows} columns={columns as any}
        pagination={{ pageSize: 8 }} />

      <Typography.Title level={5} style={{ marginTop: 12 }}>Add new LLM</Typography.Title>
      <Form form={form} layout="inline" initialValues={{ active: true }} onFinish={onSave} style={{ rowGap: 8, flexWrap: "wrap" }}>
        <Form.Item name="model_prefix" rules={[{ required: true, message: "name" }]}>
          <Input placeholder="model prefix (e.g. gemini-2.5-pro)" style={{ width: 240 }} />
        </Form.Item>
        <Form.Item name="input_cost" rules={[{ required: true }]}>
          <InputNumber placeholder="input $/1M" min={0} step={0.01} style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="output_cost" rules={[{ required: true }]}>
          <InputNumber placeholder="output $/1M" min={0} step={0.01} style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="active" label="Active" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">Save</Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}
