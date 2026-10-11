import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const i18n = fileURLToPath(new URL("../i18n", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@i18n": i18n } },
  server: {
    port: 5173,
    fs: { allow: [".", i18n] },
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { chunkSizeWarningLimit: 1200 },
});
