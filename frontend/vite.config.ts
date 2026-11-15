import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local development talks to the FastAPI service on :8000. In production the
// API is same-origin, so `/api/v1` works without a proxy.
const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
  build: {
    target: "es2022",
    sourcemap: false,
  },
});
