import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tauri expects a fixed dev server port and a relative base so the
// production build loads correctly from the WebView.
// docs/architecture/02-DESKTOP-ARCHITECTURE.md
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    outDir: "dist",
  },
});
