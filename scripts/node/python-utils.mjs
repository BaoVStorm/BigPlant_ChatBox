import { existsSync } from "node:fs";
import { access } from "node:fs/promises";
import { delimiter } from "node:path";
import { spawn, spawnSync } from "node:child_process";

const DEFAULT_CANDIDATES = [
  process.env.BIGPLANT_PYTHON,
  "/home/bigplants/miniconda3/envs/bigplants/bin/python",
  "/home/bigplants/miniconda3/bin/python",
  "python3",
  "python"
].filter(Boolean);

export function resolvePython() {
  for (const candidate of DEFAULT_CANDIDATES) {
    if (isExecutable(candidate)) {
      return candidate;
    }
  }

  throw new Error(
    "Không tìm thấy Python. Cài Python 3.10/3.11 hoặc set BIGPLANT_PYTHON=/path/to/python."
  );
}

export function runPython(args, options = {}) {
  const python = resolvePython();
  const child = spawn(python, args, {
    stdio: "inherit",
    env: { ...process.env, ...(options.env || {}) },
    cwd: options.cwd || process.cwd()
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

export function checkPythonImport(moduleName) {
  const python = resolvePython();
  const result = spawnSync(python, ["-c", `import ${moduleName}; print('ok')`], {
    encoding: "utf8",
    env: process.env
  });
  return result.status === 0;
}

export function getPythonVersion() {
  const python = resolvePython();
  const result = spawnSync(python, ["--version"], { encoding: "utf8" });
  return `${result.stdout || result.stderr}`.trim();
}

export function isExecutable(commandOrPath) {
  if (!commandOrPath) return false;

  if (commandOrPath.includes("/")) {
    return existsSync(commandOrPath);
  }

  const paths = (process.env.PATH || "").split(delimiter);
  return paths.some((path) => existsSync(`${path}/${commandOrPath}`));
}

export async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
