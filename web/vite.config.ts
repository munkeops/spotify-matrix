import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app is served under /app by FastAPI, so all built asset URLs are /app/*.
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:3000",
    },
  },
});
