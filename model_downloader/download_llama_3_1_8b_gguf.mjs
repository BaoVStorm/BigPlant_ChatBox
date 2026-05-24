import { createWriteStream, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { get } from "node:https";

const REPO_URL = "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main";
const MODEL_FILES = ["Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"];

const outputArg = process.argv[2] || "./models";
const outputDir = resolve(outputArg.endsWith(".gguf") ? dirname(outputArg) : outputArg);

try {
  console.log("Downloading Meta-Llama-3.1-8B-Instruct GGUF Q4_K_M");
  console.log(`Output directory: ${outputDir}`);

  for (const fileName of MODEL_FILES) {
    const url = `${REPO_URL}/${fileName}`;
    const outputPath = join(outputDir, fileName);
    mkdirSync(dirname(outputPath), { recursive: true });

    const existingBytes = existsSync(outputPath) ? statSync(outputPath).size : 0;
    console.log(`\nFile: ${fileName}`);
    console.log(`URL: ${url}`);
    console.log(`Output: ${outputPath}`);
    await download(url, outputPath, existingBytes);
  }

  console.log("\nModel downloaded.");
  console.log("Set LLM_MODEL_PATH=./models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf");
  console.log("Set LLM_PROMPT_FORMAT=llama3 or keep LLM_PROMPT_FORMAT=auto");
} catch (error) {
  console.error(`\n${error.message}`);
  process.exit(1);
}

function download(url, destination, resumeFrom = 0, redirectCount = 0) {
  if (redirectCount > 5) return Promise.reject(new Error("Too many redirects."));

  const headers = resumeFrom > 0 ? { Range: `bytes=${resumeFrom}-` } : {};

  return new Promise((resolveDownload, rejectDownload) => {
    const request = get(url, { headers }, (response) => {
      if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
        const location = response.headers.location;
        if (!location) {
          rejectDownload(new Error("Redirect response missing Location header."));
          return;
        }
        download(new URL(location, url).toString(), destination, resumeFrom, redirectCount + 1)
          .then(resolveDownload)
          .catch(rejectDownload);
        return;
      }

      if (![200, 206].includes(response.statusCode)) {
        rejectDownload(new Error(`Download failed with HTTP ${response.statusCode}`));
        return;
      }

      const totalBytes = parseTotalBytes(response.headers["content-length"], resumeFrom);
      const file = createWriteStream(destination, { flags: resumeFrom > 0 ? "a" : "w" });
      let downloadedBytes = resumeFrom;
      let lastPrintedAt = Date.now();

      if (resumeFrom > 0) console.log(`Resuming from ${(resumeFrom / 1024 / 1024).toFixed(2)} MB`);

      response.on("data", (chunk) => {
        downloadedBytes += chunk.length;
        const now = Date.now();
        if (now - lastPrintedAt > 1000) {
          printProgress(downloadedBytes, totalBytes);
          lastPrintedAt = now;
        }
      });

      response.pipe(file);

      file.on("finish", () => {
        file.close();
        printProgress(downloadedBytes, totalBytes);
        console.log("\nDownload completed.");
        resolveDownload();
      });

      file.on("error", (error) => rejectDownload(new Error(`File write failed: ${error.message}`)));
    });

    request.on("error", (error) => rejectDownload(new Error(`Request failed: ${error.message}`)));
  });
}

function parseTotalBytes(contentLength, resumeFrom) {
  if (!contentLength) return null;
  const remaining = Number(contentLength);
  if (!Number.isFinite(remaining)) return null;
  return remaining + resumeFrom;
}

function printProgress(downloadedBytes, totalBytes) {
  const downloadedMb = downloadedBytes / 1024 / 1024;
  if (!totalBytes) {
    process.stdout.write(`\rDownloaded ${downloadedMb.toFixed(2)} MB`);
    return;
  }
  const totalMb = totalBytes / 1024 / 1024;
  const percent = (downloadedBytes / totalBytes) * 100;
  process.stdout.write(`\rDownloaded ${downloadedMb.toFixed(2)} MB / ${totalMb.toFixed(2)} MB (${percent.toFixed(2)}%)`);
}
