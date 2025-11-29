import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Minimal default Vite config with React plugin
// This uses Vite's default dev server settings (no custom HMR/proxy/base overrides)
export default defineConfig({
  plugins: [react()],
});
