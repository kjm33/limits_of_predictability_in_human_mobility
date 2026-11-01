import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// base './' so the built site works when served from any sub-path.
export default defineConfig({
  plugins: [svelte()],
  base: "./",
  build: {
    assetsInlineLimit: 8192,
  },
});
