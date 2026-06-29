import axios from "axios";

export const api = axios.create({ baseURL: "/api" });

// attach bearer token
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// on 401, drop token so the app shows the login page
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("token");
      if (location.pathname !== "/") location.reload();
    }
    return Promise.reject(err);
  }
);

// shared query params for filtered endpoints
export interface Scope {
  project?: string;
  platform?: string;
  service?: string;
  time_range?: string;
  start?: string;
  end?: string;
}

export const get = <T = any>(url: string, params?: Record<string, any>) =>
  api.get<T>(url, { params }).then((r) => r.data);
