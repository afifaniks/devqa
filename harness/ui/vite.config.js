import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI harness server (harness/monitor.py) serves the built bundle:
//   GET /              -> dist/index.html
//   /static/assets/*   -> dist/assets/*  (StaticFiles mount)
// so the production base path is /static/. In dev (`npm run dev`), Vite serves
// from / and proxies the API to the running FastAPI server on :8766.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/" : "/",
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8766",
    },
  },
}));
