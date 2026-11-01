import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// base './' so the built site works when served from any sub-path.
// envDir '../' so the HERE key is read from the repo-root .env (git-ignored),
// not from inside demo/ — one .env for the whole project.
export default defineConfig({
  plugins: [svelte()],
  base: "./",
  envDir: "..",
  build: {
    assetsInlineLimit: 8192,
  },
});
