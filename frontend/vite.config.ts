/// <reference types="vitest/config" />
// Vite configuration (ADR-0003). One app, five route areas, each a lazy chunk.
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      port: 5173,
      strictPort: true,
      // Each business has its own address in development: mamasafi.localhost:5173.
      allowedHosts: [".localhost"],
      proxy: {
        // Same-origin API. changeOrigin stays false so Django sees the business
        // host (mamasafi.localhost) and resolves the right business (ADR-0003 4).
        "/api": { target: apiTarget, changeOrigin: false },
      },
    },
    build: {
      // dist/.vite/manifest.json: each chunk's static imports, for scripts/check-bundle.mjs.
      manifest: true,
      rollupOptions: {
        output: {
          // Readable chunk names, used by scripts/check-bundle.mjs.
          chunkFileNames: "assets/[name]-[hash].js",
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      unstubGlobals: true,
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
