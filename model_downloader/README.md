# Standalone Model Downloader

Folder này chỉ dùng để tải model local, không được import vào backend và không nằm trong flow hệ thống.

Các LLM downloader hiện có:

```txt
Qwen2.5-7B-Instruct GGUF Q4_K_M       - mặc định, cân bằng
Meta-Llama-3.1-8B-Instruct GGUF Q4_K_M - model khác họ Qwen, general/chat tốt
VinaLLaMA-7B-Chat GGUF Q5_0            - thiên tiếng Việt hơn, cũ hơn
```

Chạy bằng Node.js:

```bash
source ~/.nvm/nvm.sh
node model_downloader/download_qwen2_5_7b_gguf.mjs
```

Hoặc chạy qua npm:

```bash
npm run model:download:gwen
npm run model:download:llama
npm run model:download:vinallama
```

Tải cả 3 LLM và embedding:

```bash
npm run models:download:all
```

## Qwen2.5-7B

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

## Meta-Llama-3.1-8B

```bash
node model_downloader/download_llama_3_1_8b_gguf.mjs
```

File tải về:

```txt
models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
```

Trong `.env`:

```env
LLM_MODEL_PATH=./models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
LLM_PROMPT_FORMAT=auto
```

## VinaLLaMA-7B-Chat

```bash
node model_downloader/download_vinallama_7b_gguf.mjs
```

File tải về:

```txt
models/vinallama-7b-chat_q5_0.gguf
```

Trong `.env`:

```env
LLM_MODEL_PATH=./models/vinallama-7b-chat_q5_0.gguf
LLM_PROMPT_FORMAT=auto
```

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
