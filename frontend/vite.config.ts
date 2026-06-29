import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // For the production build, emit straight into the FastAPI static dir.
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
    allowedHosts: true,
    proxy: { "/api": "http://localhost:8001" },
  },
});
