import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Use IPv4 explicitly: on this Mac, localhost resolves to ::1, where
  // AirTunes is listening on port 5000 instead of the Flask development app.
  server: { proxy: { '/api': 'http://127.0.0.1:5000' } },
  plugins: [
    react(),
    tailwindcss(),
  ],
});
