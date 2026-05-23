import { runPython } from "./python-utils.mjs";

const useCuda = process.argv.includes("--cuda");
const env = useCuda
  ? {
      CMAKE_ARGS: "-DGGML_CUDA=on",
      FORCE_CMAKE: "1"
    }
  : {};

if (useCuda) {
  console.log("Cài Python dependencies với llama.cpp CUDA build...");
} else {
  console.log("Cài Python dependencies...");
}

runPython(["-m", "pip", "install", "-r", "requirements.txt"], { env });
