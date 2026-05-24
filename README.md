# BigPlant ChatBox

Python backend cho hybrid chatbot bán cây cảnh:

```txt
MongoDB = nguồn dữ liệu thật
Local LLM = hiểu câu hỏi + diễn giải
Local Embedding = tạo vector tiếng Việt/multilingual
MongoDB Atlas Vector Search = tìm theo ý nghĩa
RAG = trả lời kiến thức chăm cây từ knowledge base
Intent Router = quyết định flow xử lý
```

## Stack

```txt
FastAPI
pymongo
llama-cpp-python
sentence-transformers
MongoDB Atlas Vector Search
Node.js launcher scripts
```

Model khuyến nghị cho máy RTX 4060 Ti 16GB:

```txt
LLM mặc định: Qwen2.5-7B-Instruct GGUF Q4_K_M
LLM thay thế 1: Meta-Llama-3.1-8B-Instruct GGUF Q4_K_M
LLM thay thế 2: VinaLLaMA-7B-Chat GGUF Q5_0
Embedding: BAAI/bge-m3
```

## Cấu Hình

Tạo file `.env` từ `.env.example` và điền MongoDB URI thật:

```bash
cp .env.example .env
```

Các biến quan trọng:

```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.flsvljh.mongodb.net/
MONGO_DB_NAME=bigplant
LLM_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
LLM_PROMPT_FORMAT=auto
EMBEDDING_MODEL_NAME=./models/embeddings/bge-m3
EMBEDDING_DEVICE=cuda
```

Có thể đổi `LLM_MODEL_PATH` theo model đã tải:

```env
# Qwen mặc định, cân bằng chất lượng/tốc độ
LLM_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf

# Llama 3.1 8B, model khác họ Qwen, general/chat tốt
LLM_MODEL_PATH=./models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf

# VinaLLaMA 7B, thiên tiếng Việt hơn nhưng cũ hơn
LLM_MODEL_PATH=./models/vinallama-7b-chat_q5_0.gguf

# auto tự nhận Qwen/VinaLLaMA là chatml, Llama 3.x là llama3
LLM_PROMPT_FORMAT=auto
```

Không commit `.env`. File này đã được ignore.

## Cài Đặt

### Cách khuyến nghị bằng Node.js

Cài Node.js 20+ trước, sau đó dùng npm làm launcher cho backend Python:

```bash
npm run env:init
npm run deps:cuda
npm run doctor
```

Nếu không dùng CUDA cho `llama-cpp-python`:

```bash
npm run deps
```

Các script npm có sẵn:

```bash
npm run dev              # chạy FastAPI reload
npm run start            # chạy FastAPI production-style
npm run doctor           # kiểm tra Python, .env, packages, model file
npm run model:download   # alias tải Qwen2.5-7B-Instruct GGUF
npm run model:download:7b # tải Qwen2.5-7B-Instruct GGUF
npm run model:download:llama # tải Meta-Llama-3.1-8B-Instruct GGUF
npm run model:download:vinallama # tải VinaLLaMA-7B-Chat GGUF
npm run embedding:download # tải BAAI/bge-m3 về models/embeddings/
npm run models:download  # tải 7B và embedding model
npm run models:download:all # tải Qwen, Llama, VinaLLaMA và embedding model
npm run compile          # compile Python files
npm run ingest:products  # embed products vào MongoDB
npm run ingest:knowledge # embed knowledge articles vào MongoDB
```

Nếu Python không nằm ở đường dẫn mặc định, set biến `BIGPLANT_PYTHON`:

```bash
BIGPLANT_PYTHON=/path/to/python npm run dev
```

`npm run dev` và `npm run start` đọc `APP_HOST`, `APP_PORT` từ `.env`. Ví dụ muốn chạy port `3015`:

```env
APP_PORT=3015
```

### Cách chạy Python trực tiếp

Nên dùng Python 3.10 hoặc 3.11. Máy hiện có conda env `bigplants` nên có thể dùng:

```bash
conda activate bigplants
CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 python -m pip install -r requirements.txt
```

Nếu không muốn build CUDA cho `llama-cpp-python`, có thể cài CPU trước nhưng tốc độ trả lời sẽ chậm hơn.

## Tải Local LLM

Tải file GGUF vào thư mục `models/` rồi đảm bảo `LLM_MODEL_PATH` trong `.env` trỏ đúng file.

Ba lựa chọn hiện có:

| Model | Khi nên dùng | Lệnh tải | `LLM_MODEL_PATH` |
| --- | --- | --- | --- |
| Qwen2.5-7B-Instruct Q4_K_M | Cân bằng chất lượng/tốc độ, khuyến nghị mặc định | `npm run model:download:7b` | `./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` |
| Meta-Llama-3.1-8B-Instruct Q4_K_M | Muốn thử model họ Llama, general/chat tốt, tiếng Việt ổn | `npm run model:download:llama` | `./models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` |
| VinaLLaMA-7B-Chat Q5_0 | Muốn model thiên tiếng Việt, nhẹ hơn Llama 3.1 nhưng cũ hơn | `npm run model:download:vinallama` | `./models/vinallama-7b-chat_q5_0.gguf` |

Cách khuyến nghị bằng npm:

```bash
npm run model:download
```

Script này gọi file độc lập:

```txt
model_downloader/download_qwen2_5_7b_gguf.mjs
model_downloader/download_llama_3_1_8b_gguf.mjs
model_downloader/download_vinallama_7b_gguf.mjs
```

Mặc định `npm run model:download` tải model 7B dạng 2 file split GGUF:

```txt
models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
models/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf
```

Llama 3.1 8B là một file:

```txt
models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
```

VinaLLaMA 7B là một file:

```txt
models/vinallama-7b-chat_q5_0.gguf
```

Với split GGUF, `LLM_MODEL_PATH` cần trỏ tới file đầu tiên:

```env
LLM_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
```

Các file model lớn như `.gguf`, `.bin`, `.safetensors` đã được ignore trong `.gitignore`, không commit lên Git.

## Tải Embedding Model

Embedding mặc định dùng `BAAI/bge-m3`. Có 2 cách dùng:

```txt
BAAI/bge-m3                     # sentence-transformers tự tải vào cache khi chạy lần đầu
./models/embeddings/bge-m3      # dùng bản đã tải local trong project
```

Cách khuyến nghị cho dự án này là tải về local:

```bash
npm run embedding:download
```

Sau khi tải xong, cấu hình `.env`:

```env
EMBEDDING_MODEL_NAME=./models/embeddings/bge-m3
```

Folder `models/embeddings/` đã được ignore để tránh commit model embedding lên Git.

Ví dụ nếu đã có `huggingface-cli` và muốn tự tải Llama:

```bash
huggingface-cli download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --local-dir models --local-dir-use-symlinks False
```

## Chạy API

Chạy bằng npm:

```bash
npm run dev
```

Hoặc chạy Python trực tiếp:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Chat API:

```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","message":"Tôi muốn cây dễ chăm để bàn làm việc dưới 300k"}'
```

## Ingest Vector

Embed products vào collection `products`:

```bash
npm run ingest:products
```

Hoặc:

```bash
python scripts/ingest_products.py
```

Embed articles từ `plant_knowledge_articles` vào `knowledge_chunks`:

```bash
npm run ingest:knowledge
```

Hoặc:

```bash
python scripts/ingest_knowledge.py
```

## MongoDB Atlas Vector Search

Tạo vector index cho `products` với path mặc định:

```txt
embedding
```

Tên index:

```txt
product_vector_index
```

Tạo vector index cho `knowledge_chunks` với path mặc định:

```txt
embedding
```

Tên index:

```txt
knowledge_vector_index
```

Nếu dùng `BAAI/bge-m3`, dimension thường là `1024`. Cần cấu hình đúng dimension trên Atlas.

## Flow Đã Có

```txt
POST /api/chat/message
 ↓
IntentRouter
 ├── product_info      → MongoDB products/variants/images
 ├── recommendation    → MongoDB filter + Vector Search
 ├── plant_care        → RAG knowledge_chunks
 ├── cart_order        → placeholder để nối Cart API
 └── general           → Local LLM hoặc fallback
```

LLM local không được dùng để tự bịa giá, tồn kho hoặc size. Các thông tin đó luôn lấy từ MongoDB.
