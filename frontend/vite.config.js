import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Dev: /v1 aur /health requests FastAPI (port 8000) pe proxy -> same-origin, CORS ki zaroorat nahi.
// `npm run dev:phone` (mode "phone"): self-signed HTTPS, taaki phone LAN pe camera chala sake
// (getUserMedia sirf HTTPS ya localhost pe milta hai).
export default defineConfig(({ mode }) => ({
  plugins: [
    ...(mode === "phone" ? [basicSsl()] : []),
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "FaceAI Pro",
        short_name: "FaceAI",
        description: "Face recognition attendance",
        theme_color: "#701a27",
        background_color: "#f7f4ef",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Offline: app shell + PEHLE dekhe gaye GET reports (read-only). Attendance marking kabhi
        // cache se nahi (POST network-only), warna offline "present" ka jhootha bharosa milta.
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/v1\//, /^\/health/, /^\/metrics/],
        runtimeCaching: [
          {
            urlPattern: ({ url, request }) =>
              request.method === "GET" && /^\/v1\/(me|admin\/(overview|attendance|reports|students|batches))/.test(url.pathname),
            handler: "NetworkFirst",
            options: { cacheName: "api-read", networkTimeoutSeconds: 4, expiration: { maxEntries: 60, maxAgeSeconds: 86400 } },
          },
        ],
      },
    }),
  ],
  server: {
    host: true, // phone se LAN pe test (camera ke liye HTTPS/localhost chahiye - docs dekho)
    proxy: { "/v1": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.js"], globals: true },
}));
