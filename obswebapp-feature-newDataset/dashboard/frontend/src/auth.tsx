import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";

interface AuthCtx {
  token: string | null;
  user: string | null;
  login: (u: string, p: string) => Promise<void>;
  loginGoogle: (credential: string) => Promise<void>;
  loginIap: () => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<string | null>(localStorage.getItem("user"));

  const setSession = (data: any) => {
    localStorage.setItem("token", data.token);
    localStorage.setItem("user", data.user);
    setToken(data.token);
    setUser(data.user);
  };

  // Sign in using the IAP-verified identity (works because IAP already authenticated the browser).
  const loginIap = async () => {
    const { data } = await api.get("/auth/iap");
    setSession(data);
  };

  // Behind IAP, auto-issue a session on first load — skip the login page.
  useEffect(() => {
    if (!token) loginIap().catch(() => { /* not behind IAP (local dev) — show the form */ });
  }, []);

  const login = async (u: string, p: string) => {
    const { data } = await api.post("/login", { username: u, password: p });
    setSession(data);
  };

  const loginGoogle = async (credential: string) => {
    const { data } = await api.post("/login/google", { credential });
    setSession(data);
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
  };

  return <Ctx.Provider value={{ token, user, login, loginGoogle, loginIap, logout }}>{children}</Ctx.Provider>;
}
