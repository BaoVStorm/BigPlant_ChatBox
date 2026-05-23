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
LLM: Qwen2.5-7B-Instruct GGUF Q4_K_M
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
LLM_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m.gguf
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DEVICE=cuda
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
npm run model:download   # tải Qwen2.5-7B-Instruct GGUF về models/
npm run compile          # compile Python files
npm run ingest:products  # embed products vào MongoDB
npm run ingest:knowledge # embed knowledge articles vào MongoDB
```

Nếu Python không nằm ở đường dẫn mặc định, set biến `BIGPLANT_PYTHON`:

```bash
BIGPLANT_PYTHON=/path/to/python npm run dev
```

### Cách chạy Python trực tiếp

Nên dùng Python 3.10 hoặc 3.11. Máy hiện có conda env `bigplants` nên có thể dùng:

```bash
conda activate bigplants
CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 python -m pip install -r requirements.txt
```

Nếu không muốn build CUDA cho `llama-cpp-python`, có thể cài CPU trước nhưng tốc độ trả lời sẽ chậm hơn.

## Tải Local LLM

Tải file GGUF Qwen2.5-7B-Instruct Q4_K_M vào thư mục `models/` rồi đảm bảo tên trùng `LLM_MODEL_PATH` trong `.env`.

Cách khuyến nghị bằng npm:

```bash
npm run model:download
```

Script này gọi file độc lập:

```txt
model_downloader/download_qwen2_5_7b_gguf.mjs
```

Mặc định model được tải về:

```txt
models/qwen2.5-7b-instruct-q4_k_m.gguf
```

Các file model lớn như `.gguf`, `.bin`, `.safetensors` đã được ignore trong `.gitignore`, không commit lên Git.

Ví dụ nếu đã có `huggingface-cli`:

```bash
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_k_m.gguf --local-dir models --local-dir-use-symlinks False
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
