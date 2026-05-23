import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { checkPythonImport, getPythonVersion, resolvePython } from "./python-utils.mjs";

const requiredEnvKeys = ["MONGO_URI", "MONGO_DB_NAME", "LLM_MODEL_PATH", "EMBEDDING_MODEL_NAME"];
const requiredImports = [
  "fastapi",
  "uvicorn",
  "pymongo",
  "pydantic",
  "pydantic_settings",
  "sentence_transformers",
  "llama_cpp",
  "bs4",
  "numpy"
];

console.log("BigPlant ChatBox doctor");
console.log(`Node: ${process.version}`);

try {
  console.log(`Python: ${resolvePython()} (${getPythonVersion()})`);
} catch (error) {
  fail(error.message);
}

if (!existsSync(".env")) {
  warn("Thiếu .env. Chạy: npm run env:init");
} else {
  const env = parseEnv(readFileSync(".env", "utf8"));
  for (const key of requiredEnvKeys) {
    if (!env[key] || env[key].includes("<")) {
      warn(`.env thiếu hoặc chưa cấu hình ${key}`);
    } else {
      ok(`${key} đã cấu hình`);
    }
  }

  if (env.LLM_MODEL_PATH) {
    const modelPath = resolve(env.LLM_MODEL_PATH);
    if (existsSync(modelPath)) {
      ok(`Local LLM model tồn tại: ${modelPath}`);
    } else {
      warn(`Chưa thấy local LLM model: ${modelPath}`);
    }
  }
}

for (const moduleName of requiredImports) {
  if (checkPythonImport(moduleName)) {
    ok(`Python import ${moduleName}`);
  } else {
    warn(`Thiếu Python package ${moduleName}. Chạy: npm run deps:cuda`);
  }
}

console.log("Doctor hoàn tất.");

function parseEnv(content) {
  const result = {};
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const index = trimmed.indexOf("=");
    if (index === -1) continue;
    result[trimmed.slice(0, index)] = trimmed.slice(index + 1);
  }
  return result;
}

function ok(message) {
  console.log(`[OK] ${message}`);
}

function warn(message) {
  console.warn(`[WARN] ${message}`);
}

function fail(message) {
  console.error(`[ERROR] ${message}`);
  process.exit(1);
}
