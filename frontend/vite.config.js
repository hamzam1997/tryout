import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Flask app owns these paths; everything else is the React app.
const API_ROUTES = ["/meetings", "/ideas", "/health"];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_ROUTES.map((path) => [path, { target: "http://localhost:8080", changeOrigin: true }])
    ),
  },
  build: {
    outDir: "dist",
  },
});
