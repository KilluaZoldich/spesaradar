import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({ mode }) => ({
  base: loadEnv(mode, ".").VITE_BASE_PATH || "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 8080,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
}));
