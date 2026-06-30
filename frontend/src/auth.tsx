import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";

export type Role = "admin" | "user";

interface AuthCtx {
  token: string | null;
  user: string | null;
  role: Role | null;
  allowedProjects: string[];
  login: (u: string, p: string) => Promise<void>;
  loginGoogle: (credential: string) => Promise<void>;
  loginIap: () => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

function readArr(key: string): string[] {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : [];
  } catch {
    return [];
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<string | null>(localStorage.getItem("user"));
  const [role, setRole] = useState<Role | null>((localStorage.getItem("role") as Role) || null);
  const [allowedProjects, setAllowedProjects] = useState<string[]>(readArr("allowedProjects"));

  const setSession = (data: any) => {
    localStorage.setItem("token", data.token);
    localStorage.setItem("user", data.user);
    if (data.role) localStorage.setItem("role", data.role);
    if (Array.isArray(data.allowed_projects))
      localStorage.setItem("allowedProjects", JSON.stringify(data.allowed_projects));
    setToken(data.token);
    setUser(data.user);
    setRole(data.role || null);
    setAllowedProjects(data.allowed_projects || []);
  };

  // Sign in using the IAP-verified identity (works because IAP already authenticated the browser).
  const loginIap = async () => {
    const { data } = await api.get("/auth/iap");
    setSession(data);
  };

  const refreshMe = async () => {
    try {
      const { data } = await api.get("/me");
      localStorage.setItem("role", data.role);
      localStorage.setItem("allowedProjects", JSON.stringify(data.allowed_projects || []));
      setRole(data.role);
      setAllowedProjects(data.allowed_projects || []);
    } catch {
      /* ignore */
    }
  };

  // Behind IAP, auto-issue a session on first load — skip the login page.
  useEffect(() => {
    if (!token) loginIap().catch(() => { /* not behind IAP (local dev) — show the form */ });
    else if (!role) refreshMe();
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
    localStorage.removeItem("role");
    localStorage.removeItem("allowedProjects");
    setToken(null);
    setUser(null);
    setRole(null);
    setAllowedProjects([]);
  };

  return (
    <Ctx.Provider value={{ token, user, role, allowedProjects, login, loginGoogle, loginIap, logout, refreshMe }}>
      {children}
    </Ctx.Provider>
  );
}
