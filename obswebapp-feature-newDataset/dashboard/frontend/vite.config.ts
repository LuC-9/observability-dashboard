import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: frontend calls /api/* -> backend on :8000 (no CORS pain in dev).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
