# Models And Embedding

## 1. Local LLM trong app dùng để làm gì

Local LLM hiện không được dùng cho mọi flow.

Hiện tại nó chủ yếu được dùng cho:

```txt
router fallback khi rules + semantic chưa chắc
general chat
plant care sau khi đã có context
```

Nó không được dùng để trả lời trực tiếp cho:

```txt
product_info factual
recommendation factual
```

## 2. Ba model LLM hiện có trong app

### Qwen2.5-7B-Instruct Q4_K_M

Vai trò:

```txt
model mặc định hiện tại của app
```

Điểm mạnh:

```txt
tiếng Việt ổn
instruction following tốt
chat tự nhiên
ổn định cho general chat và router fallback
```

Điểm yếu:

```txt
nếu chạy CPU-only vẫn chậm
```

### Meta-Llama-3.1-8B-Instruct Q4_K_M

Vai trò:

```txt
model thay thế để benchmark chất lượng general / reasoning
```

Điểm mạnh:

```txt
reasoning tốt
general chat tốt
```

Điểm yếu:

```txt
tiếng Việt không đều bằng Qwen ở một số tình huống
```

### VinaLLaMA-7B-Chat Q5_0

Vai trò:

```txt
model thay thế thiên tiếng Việt
```

Điểm mạnh:

```txt
phù hợp để test hội thoại tiếng Việt
```

Điểm yếu:

```txt
cũ hơn
reasoning yếu hơn Qwen và Llama 3.1
tuân thủ instruction không tốt bằng Qwen
```

## 3. Embedding model đang dùng

Embedding model hiện tại:

```txt
BAAI/bge-m3
```

## 4. Embedding được dùng ở đâu

### Semantic router

```txt
embed câu user
→ so với ví dụ intent
→ chọn intent gần nghĩa nhất
```

### Recommendation

```txt
embed query recommendation
→ search product vector index
→ lấy candidate semantic
→ query lại MongoDB để lấy dữ liệu thật
```

### Plant Care / RAG

```txt
embed câu hỏi plant care
→ search knowledge vector index
→ lấy top context chunks
→ đưa cho LLM diễn giải
```

## 5. Vai trò thật của embedding trong app

Embedding không trả lời trực tiếp.

Embedding chỉ giúp app:

```txt
hiểu câu gần nghĩa
tìm sản phẩm gần nghĩa
tìm tài liệu gần nghĩa
```
