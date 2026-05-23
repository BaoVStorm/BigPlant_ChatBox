import { copyFileSync, existsSync } from "node:fs";

if (existsSync(".env")) {
  console.log(".env đã tồn tại, không ghi đè.");
  process.exit(0);
}

if (!existsSync(".env.example")) {
  console.error("Không tìm thấy .env.example.");
  process.exit(1);
}

copyFileSync(".env.example", ".env");
console.log("Đã tạo .env từ .env.example.");
console.log("Hãy điền MONGO_URI thật và LLM_MODEL_PATH trước khi chạy API.");
