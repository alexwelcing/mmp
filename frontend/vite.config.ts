import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
  server: {
    port: 5173,
    // Proxy API calls to the AI Director during local development.
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    // Increase chunk size warning limit for 3D viewer dependencies.
    chunkSizeWarningLimit: 1000,
  },
  define: {
    // Make environment variables available to the frontend bundle.
    __AI_DIRECTOR_URL__: JSON.stringify(
      process.env.VITE_AI_DIRECTOR_URL ?? "http://localhost:8080"
    ),
  },
});
