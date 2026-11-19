import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      // Two pages: the English landing page at / and the Hindi one at /hi/.
      input: {
        main: resolve(__dirname, "index.html"),
        hi: resolve(__dirname, "hi/index.html"),
      },
    },
  },
});
