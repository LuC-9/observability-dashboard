import { useEffect, useState } from "react";
import { Card, Form, Input, Button, Typography, Divider, App, Alert } from "antd";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import { useAuth } from "../auth";
import { BRAND } from "../theme";
import { get } from "../api";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

interface PublicConfig {
  google_client_id?: string;
  allowed_domain?: string;
}

export default function Login() {
  const { login, loginGoogle } = useAuth();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);

  useEffect(() => {
    get<PublicConfig>("/config")
      .then((c) => setCfg(c || {}))
      .catch(() => setCfg({}));
  }, []);

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true);
    try { await login(v.username, v.password); }
    catch { message.error("Invalid username or password"); }
    finally { setLoading(false); }
  };

  const onGoogle = async (credential: string) => {
    try { await loginGoogle(credential); }
    catch (e: any) {
      const msg = e?.response?.data?.detail || "Google sign-in failed";
      message.error(msg);
    }
  };

  // While we don't know the config yet, render a minimal placeholder
  // so we don't flash the password form to SSO-only users.
  if (cfg === null) {
    return (
      <div data-testid="login-page-loading" style={shellStyle}>
        <Card style={cardStyle} loading />
      </div>
    );
  }

  const hasGoogle = Boolean(cfg.google_client_id);
  const hd = cfg.allowed_domain || undefined;

  const card = (
    <Card style={cardStyle}>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0, color: BRAND.ink }}>GenAI Observability</Typography.Title>
        <Typography.Text type="secondary">Central platform · L'Oréal</Typography.Text>
      </div>

      {hasGoogle && (
        <>
          <div data-testid="login-google-wrap" style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
            <GoogleLogin
              hosted_domain={hd}
              onSuccess={(r) => r.credential && onGoogle(r.credential)}
              onError={() => message.error("Google sign-in was cancelled or failed")}
              theme="filled_blue"
              shape="pill"
              size="large"
              text="signin_with"
              width="320"
            />
          </div>
          {hd && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={<span data-testid="login-domain-hint">Use your <b>@{hd}</b> Google account</span>}
            />
          )}
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
        <Button data-testid="login-submit" type="primary" htmlType="submit" block size="large" loading={loading}>
          Sign in
        </Button>
      </Form>
    </Card>
  );

  return (
    <div data-testid="login-page" style={shellStyle}>
      {hasGoogle
        ? <GoogleOAuthProvider clientId={cfg.google_client_id!}>{card}</GoogleOAuthProvider>
        : card}
    </div>
  );
}

const shellStyle: React.CSSProperties = {
  minHeight: "100vh",
  display: "grid",
  placeItems: "center",
  background: `linear-gradient(135deg, ${BRAND.black} 0%, #2a2317 100%)`,
};

const cardStyle: React.CSSProperties = {
  width: 400,
  borderTop: `4px solid ${BRAND.gold}`,
};
