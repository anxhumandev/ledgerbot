import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = process.env.TESSERA_API ?? "http://127.0.0.1:8100";
const PORT = Number(process.env.FRONTEND_PORT ?? 5174);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: PORT,
    strictPort: true,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/ws": { target: API.replace("http", "ws"), ws: true },
    },
  },
});
