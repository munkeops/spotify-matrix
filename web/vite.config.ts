import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app is served at the site root by FastAPI; built asset URLs are /assets/*.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:3000",
    },
  },
});
