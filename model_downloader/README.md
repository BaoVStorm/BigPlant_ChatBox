# Standalone Model Downloader

Folder này chỉ dùng để tải model local, không được import vào backend và không nằm trong flow hệ thống.

Model mặc định:

```txt
Qwen2.5-7B-Instruct GGUF Q4_K_M
```

Chạy bằng Node.js:

```bash
source ~/.nvm/nvm.sh
node model_downloader/download_qwen2_5_7b_gguf.mjs
```

Mặc định file sẽ được tải về:

```txt
models/qwen2.5-7b-instruct-q4_k_m.gguf
```

Muốn đổi nơi lưu:

```bash
node model_downloader/download_qwen2_5_7b_gguf.mjs /duong/dan/toi/model.gguf
```

Script có hỗ trợ resume nếu file tải dở đã tồn tại.
