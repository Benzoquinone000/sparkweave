import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  envPrefix: ["VITE_", "NEXT_PUBLIC_"],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: Number(process.env.FRONTEND_PORT || 3782),
    strictPort: false,
  },
  preview: {
    host: "0.0.0.0",
    port: Number(process.env.FRONTEND_PORT || 3782),
    strictPort: false,
  },
  build: {
    // Mermaid and its diagram engines are loaded only when a visualization result is opened.
    chunkSizeWarningLimit: 3000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          const normalized = id.replaceAll("\\", "/");
          if (normalized.includes("/node_modules/react-dom") || normalized.includes("/node_modules/scheduler")) {
            return "react-dom";
          }
          if (normalized.includes("/node_modules/react/") || normalized.includes("/node_modules/react/jsx")) {
            return "react";
          }
          if (
            normalized.includes("/node_modules/mermaid") ||
            normalized.includes("/node_modules/@mermaid-js") ||
            normalized.includes("/node_modules/chevrotain") ||
            normalized.includes("/node_modules/chevrotain-allstar") ||
            normalized.includes("/node_modules/cose-base") ||
            normalized.includes("/node_modules/cytoscape") ||
            normalized.includes("/node_modules/d3") ||
            normalized.includes("/node_modules/dagre") ||
            normalized.includes("/node_modules/dagre-d3-es") ||
            normalized.includes("/node_modules/dompurify") ||
            normalized.includes("/node_modules/elkjs") ||
            normalized.includes("/node_modules/katex") ||
            normalized.includes("/node_modules/khroma") ||
            normalized.includes("/node_modules/langium") ||
            normalized.includes("/node_modules/layout-base") ||
            normalized.includes("/node_modules/lodash-es") ||
            normalized.includes("/node_modules/marked") ||
            normalized.includes("/node_modules/roughjs")
          ) {
            return "visualization";
          }
          if (normalized.includes("/node_modules/chart.js") || normalized.includes("/node_modules/@kurkle")) {
            return "charts";
          }
          if (
            normalized.includes("/node_modules/react-markdown") ||
            normalized.includes("/node_modules/remark-") ||
            normalized.includes("/node_modules/rehype-") ||
            normalized.includes("/node_modules/unified") ||
            normalized.includes("/node_modules/micromark") ||
            normalized.includes("/node_modules/mdast-") ||
            normalized.includes("/node_modules/hast-") ||
            normalized.includes("/node_modules/unist-") ||
            normalized.includes("/node_modules/vfile") ||
            normalized.includes("/node_modules/bail") ||
            normalized.includes("/node_modules/ccount") ||
            normalized.includes("/node_modules/character-") ||
            normalized.includes("/node_modules/comma-separated-tokens") ||
            normalized.includes("/node_modules/decode-named-character-reference") ||
            normalized.includes("/node_modules/devlop") ||
            normalized.includes("/node_modules/estree-util") ||
            normalized.includes("/node_modules/html-url-attributes") ||
            normalized.includes("/node_modules/is-plain-obj") ||
            normalized.includes("/node_modules/markdown-table") ||
            normalized.includes("/node_modules/parse-entities") ||
            normalized.includes("/node_modules/property-information") ||
            normalized.includes("/node_modules/space-separated-tokens") ||
            normalized.includes("/node_modules/stringify-entities") ||
            normalized.includes("/node_modules/trim-lines") ||
            normalized.includes("/node_modules/trough") ||
            normalized.includes("/node_modules/zwitch")
          ) {
            return "markdown";
          }
          if (normalized.includes("/node_modules/@tanstack")) return "tanstack";
          if (normalized.includes("/node_modules/framer-motion")) return "motion";
          if (normalized.includes("/node_modules/lucide-react")) return "icons";
          return "vendor";
        },
      },
    },
  },
});
