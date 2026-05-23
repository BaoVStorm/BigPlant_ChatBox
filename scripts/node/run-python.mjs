import { runPython } from "./python-utils.mjs";

const args = process.argv.slice(2);

if (args.length === 0) {
  console.error("Thiếu Python args. Ví dụ: npm run dev");
  process.exit(1);
}

runPython(args);
