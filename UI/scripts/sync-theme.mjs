// Regenerates src/theme.css from the single shared source of truth
// (Shared/webui/theme.css, a sibling of this UI/ directory) before every
// dev/build command — see the "pre*" hooks in package.json. Keeps the
// brand palette/fonts identical across Krouzek, AccessRequest, Projects
// and the three builds in this React app without hand-copying it.
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "..", "Shared", "webui", "theme.css");
const dest = join(here, "..", "src", "theme.css");

copyFileSync(source, dest);
console.log(`synced ${dest} from ${source}`);
