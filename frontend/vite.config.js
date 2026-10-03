import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxying the API in dev avoids CORS issues; /docs serves Swagger from the backend.
const target = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/docs": { target, changeOrigin: true },
      "/openapi.json": { target, changeOrigin: true },
    },
  },
});
