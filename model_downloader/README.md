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

Mặc định model sẽ được tải về dạng 2 file split GGUF:

```txt
models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
models/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf
```

Trong `.env`, cấu hình `LLM_MODEL_PATH` trỏ tới shard đầu tiên:

```env
LLM_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
```

Muốn đổi thư mục lưu:

```bash
node model_downloader/download_qwen2_5_7b_gguf.mjs /duong/dan/toi/models
```

Script có hỗ trợ resume nếu file tải dở đã tồn tại.

## Embedding Model

Tải `BAAI/bge-m3` về local:

```bash
node model_downloader/download_bge_m3_embedding.mjs
```

Mặc định tải vào:

```txt
models/embeddings/bge-m3
```

Sau đó cấu hình `.env`:

```env
EMBEDDING_MODEL_NAME=./models/embeddings/bge-m3
```

Muốn đổi thư mục lưu:

```bash
node model_downloader/download_bge_m3_embedding.mjs /duong/dan/toi/bge-m3
```
