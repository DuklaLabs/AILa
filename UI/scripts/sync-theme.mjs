// Regenerates src/theme.css and src/theme-toggle.js from the single shared
// source of truth (Shared/webui/, a sibling of this UI/ directory) before
// every dev/build command — see the "pre*" hooks in package.json. Keeps the
// brand palette/fonts and the light/dark switch identical across Krouzek,
// AccessRequest, Projects and the three builds in this React app without
// hand-copying them.
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

for (const name of ["theme.css", "theme-toggle.js"]) {
  const source = join(here, "..", "..", "Shared", "webui", name);
  const dest = join(here, "..", "src", name);
  copyFileSync(source, dest);
  console.log(`synced ${dest} from ${source}`);
}
