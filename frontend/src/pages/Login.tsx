import { useEffect, useState } from "react";
import { Card, Form, Input, Button, Typography, Divider, App } from "antd";
import { GoogleOutlined } from "@ant-design/icons";
import { useAuth } from "../auth";
import { BRAND } from "../theme";
import { get } from "../api";

export default function Login() {
  const { login, loginIap } = useAuth();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [sso, setSso] = useState(false);
  const [hasGoogle, setHasGoogle] = useState(false);

  useEffect(() => {
    get<{ google_client_id?: string }>("/config")
      .then((c) => setHasGoogle(Boolean(c?.google_client_id)))
      .catch(() => setHasGoogle(false));
  }, []);

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true);
    try { await login(v.username, v.password); }
    catch { message.error("Invalid username or password"); }
    finally { setLoading(false); }
  };

  const onGoogle = async () => {
    setSso(true);
    try { await loginIap(); }
    catch {
      message.error("Google sign-in unavailable here. If this isn't behind IAP, use username/password.");
    } finally { setSso(false); }
  };

  return (
    <div data-testid="login-page" style={{ minHeight: "100vh", display: "grid", placeItems: "center",
                  background: `linear-gradient(135deg, ${BRAND.black} 0%, #2a2317 100%)` }}>
      <Card style={{ width: 380, borderTop: `4px solid ${BRAND.gold}` }}>
        <div style={{ textAlign: "center", marginBottom: 16 }}>
          <Typography.Title level={3} style={{ margin: 0, color: BRAND.ink }}>GenAI Observability</Typography.Title>
          <Typography.Text type="secondary">Central platform · L'Oréal</Typography.Text>
        </div>

        {hasGoogle && (
          <>
            <Button data-testid="login-google-btn" block size="large" icon={<GoogleOutlined />} loading={sso} onClick={onGoogle}>
              Sign in with Google
            </Button>
            <Divider plain style={{ color: "#999" }}>or username</Divider>
          </>
        )}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input data-testid="login-username" size="large" autoFocus />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true }]}>
            <Input.Password data-testid="login-password" size="large" />
          </Form.Item>
          <Button data-testid="login-submit" type="primary" htmlType="submit" block size="large" loading={loading}>Sign in</Button>
        </Form>
      </Card>
    </div>
  );
}
