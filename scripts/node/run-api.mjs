import { existsSync, readFileSync } from "node:fs";
import { runPython, resolvePython } from "./python-utils.mjs";

const env = parseEnvFile(".env");
const host = process.env.APP_HOST || env.APP_HOST || "0.0.0.0";
const port = process.env.APP_PORT || env.APP_PORT || "8000";
const reload = process.argv.includes("--reload");
const printOnly = process.argv.includes("--print");

const args = ["-m", "uvicorn", "app.main:app", "--host", host, "--port", String(port)];
if (reload) {
  args.push("--reload");
}

if (printOnly) {
  console.log(`${resolvePython()} ${args.join(" ")}`);
  process.exit(0);
}

runPython(args);

function parseEnvFile(path) {
  if (!existsSync(path)) return {};

  const result = {};
  const content = readFileSync(path, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const index = trimmed.indexOf("=");
    if (index === -1) continue;
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, "");
    result[key] = value;
  }
  return result;
}
