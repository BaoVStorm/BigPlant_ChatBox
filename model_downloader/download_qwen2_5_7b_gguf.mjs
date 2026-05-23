import { createWriteStream, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { get } from "node:https";

const MODEL_URL =
  "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf";

const outputPath = resolve(
  process.argv[2] || "./models/qwen2.5-7b-instruct-q4_k_m.gguf"
);

mkdirSync(dirname(outputPath), { recursive: true });

const existingBytes = existsSync(outputPath) ? statSync(outputPath).size : 0;

console.log("Downloading Qwen2.5-7B-Instruct GGUF Q4_K_M");
console.log(`URL: ${MODEL_URL}`);
console.log(`Output: ${outputPath}`);

download(MODEL_URL, outputPath, existingBytes);

function download(url, destination, resumeFrom = 0, redirectCount = 0) {
  if (redirectCount > 5) {
    console.error("Too many redirects.");
    process.exit(1);
  }

  const headers = resumeFrom > 0 ? { Range: `bytes=${resumeFrom}-` } : {};

  const request = get(url, { headers }, (response) => {
    if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
      const location = response.headers.location;
      if (!location) {
        console.error("Redirect response missing Location header.");
        process.exit(1);
      }
      const nextUrl = new URL(location, url).toString();
      download(nextUrl, destination, resumeFrom, redirectCount + 1);
      return;
    }

    if (![200, 206].includes(response.statusCode)) {
      console.error(`Download failed with HTTP ${response.statusCode}`);
      process.exit(1);
    }

    const totalBytes = parseTotalBytes(response.headers["content-length"], resumeFrom);
    const file = createWriteStream(destination, { flags: resumeFrom > 0 ? "a" : "w" });
    let downloadedBytes = resumeFrom;
    let lastPrintedAt = Date.now();

    if (resumeFrom > 0) {
      console.log(`Resuming from ${(resumeFrom / 1024 / 1024).toFixed(2)} MB`);
    }

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
    });

    file.on("error", (error) => {
      console.error(`File write failed: ${error.message}`);
      process.exit(1);
    });
  });

  request.on("error", (error) => {
    console.error(`Request failed: ${error.message}`);
    process.exit(1);
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
  process.stdout.write(
    `\rDownloaded ${downloadedMb.toFixed(2)} MB / ${totalMb.toFixed(2)} MB (${percent.toFixed(2)}%)`
  );
}
