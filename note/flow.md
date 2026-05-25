# BigPlant AI Flow

File này mô tả chi tiết luồng source code hiện tại đang xử lý request chat như thế nào, chia nhánh ra sao, query collection nào, flow nào dùng LLM và flow nào không dùng LLM. Mục tiêu là dùng làm tài liệu mô tả flow AI/hệ thống cho slide.

## 1. Mục tiêu của flow

Hệ thống hiện tại không dùng một prompt LLM duy nhất cho mọi câu hỏi. Thay vào đó, request được phân loại trước, sau đó đi vào từng nhánh xử lý riêng.

Nguyên tắc hiện tại:

```txt
MongoDB là nguồn dữ liệu thật.
LLM không được tự bịa giá, tồn kho, variant, ảnh, độc tính.
LLM hiện chỉ giữ vai trò mạnh ở general chat và các flow cần diễn giải context.
Product Info và Recommendation hiện đang trả lời deterministic để đảm bảo nhanh và đúng dữ liệu.
```

## 2. Entry point của hệ thống

API chính:

```txt
POST /api/chat/message
```

File entry route:

```txt
app/chat/chat_router.py
```

Schema request:

```txt
message: string
user_id: optional string
session_id: optional string
```

Schema response:

```txt
intent: string
message: string
products: list
sources: list
metadata: object
```

## 3. Tổng quan request lifecycle

Khi user gửi một message, hệ thống đi theo chuỗi sau:

```txt
HTTP request
→ FastAPI route
→ singleton ChatService
→ IntentRouter.classify(message)
→ switch theo intent
→ handler tương ứng
→ trả response JSON
```

Chi tiết hơn:

```txt
1. FastAPI nhận request POST /api/chat/message
2. Payload được validate bằng Pydantic
3. Route lấy ChatService singleton qua lru_cache
4. ChatService đo thời gian route và handler
5. Router phân loại intent + extract entities
6. ChatService dispatch sang handler tương ứng
7. Handler query MongoDB hoặc LLM tùy flow
8. Response được chuẩn hóa thành ChatMessageResponse
9. metadata.timing_ms được gắn vào kết quả
```

## 4. Thành phần chính trong code

Các file chịu trách nhiệm hiện tại:

```txt
app/chat/chat_router.py            → FastAPI endpoint /api/chat/message
app/chat/chat_service.py           → điều phối toàn bộ message
app/router/intent_router.py        → router + entity extraction
app/products/product_repository.py → query MongoDB và build full product context
app/products/product_handler.py    → Product Info flow
app/recommendations/recommendation_handler.py → Recommendation flow
app/knowledge/rag_handler.py       → Plant Care / knowledge flow
app/llm/local_llm.py               → local LLM loader + generate
app/embeddings/embedding_service.py → local embedding model
```

## 5. ChatService đang làm gì

File:

```txt
app/chat/chat_service.py
```

Khi khởi tạo, ChatService tạo và giữ:

```txt
LocalLLM
IntentRouter
ProductRepository
ProductInfoHandler
RecommendationHandler
PlantCareRagHandler
```

Luồng chính trong `handle_message`:

```txt
1. bắt đầu timer tổng
2. gọi router.classify(message)
3. đo route time
4. switch theo route.intent
5. gọi handler tương ứng
6. đo handler time
7. gắn metadata:
   - user_id
   - session_id
   - timing_ms.route
   - timing_ms.handler
   - timing_ms.total
8. trả kết quả
```

## 6. Intent Router hoạt động thế nào

File:

```txt
app/router/intent_router.py
```

Router hiện tại là hybrid nhưng nghiêng mạnh về heuristic.

### 6.1. Bước normalize text

Trước khi classify, router:

```txt
1. lower-case text
2. bỏ dấu tiếng Việt
3. co cụm khoảng trắng
```

Mục đích:

```txt
"Cây có độc với mèo không?"
→ "cay co doc voi meo khong?"
```

Giúp heuristic match ổn định hơn.

### 6.2. Entity extraction hiện tại

Router extract một số entity trước cả khi quyết định intent:

```txt
product_name
max_price
care_level
watering_need
light_requirement
placement
pet_safe
```

Chi tiết:

```txt
product_name:
  - regex theo pattern "cây <name> ..."
  - hoặc pattern "giá <name>"

max_price:
  - parse các mẫu như dưới 300k, khoảng 500k, 1 triệu

care_level:
  - gắn "easy" nếu có các từ như dễ chăm, người mới, ít chăm

watering_need:
  - gắn "low" nếu có các từ như hay quên tưới, ít tưới, bận rộn

light_requirement:
  - gắn "low" nếu có các từ như ít nắng, thiếu sáng
  - gắn "indirect" nếu có ánh sáng gián tiếp

placement:
  - desk / office / bedroom / living_room theo cụm từ Việt

pet_safe:
  - gắn true nếu câu nhắc tới mèo/chó/thú cưng
```

Lưu ý quan trọng:

```txt
Một số entity như watering_need, light_requirement, placement hiện được extract ra,
nhưng DB hiện tại chưa có field cứng tương ứng trong products.
Vì vậy chúng chủ yếu phục vụ vector search / semantic matching,
không phải hard filter trực tiếp trong MongoDB.
```

### 6.3. Heuristic classification

Router dùng danh sách marker để chia intent.

#### cart_order

Nếu text chứa các marker như:

```txt
them vao gio
gio hang
dat hang
mua ngay
checkout
thanh toan
```

thì intent = `cart_order`.

#### recommendation

Nếu text chứa các marker như:

```txt
tu van
goi y
nen mua
nen chon
chon cay
cay nao
toi muon cay
phu hop
lam qua
de ban
phong khach
phong ngu
van phong
```

thì intent = `recommendation`.

#### plant_care

Nếu text chứa các marker như:

```txt
vang la
ung re
thoi re
heo la
dom la
sau benh
bi benh
tai sao
xu ly sao
cham soc
tuoi bao lau
bao lau tuoi
nen tuoi
```

thì intent = `plant_care`.

#### product_info

Nếu text chứa các marker như:

```txt
bao nhieu tien
gia
con hang
het hang
ton kho
size
kich thuoc
hinh anh
anh san pham
co doc
doc voi
an toan cho thu cung
```

thì intent = `product_info`.

#### general

Nếu text chứa:

```txt
xin chao
hello
hi
cam on
```

thì intent = `general`.

#### unclear

Nếu không match heuristic nào, router trả `unclear`.

### 6.4. Khi nào router gọi local LLM

Hiện tại router chỉ gọi LLM khi:

```txt
heuristic_route.intent == unclear
AND local LLM available
```

Nghĩa là:

```txt
Câu rõ ràng → không gọi LLM để route
Câu mơ hồ → có thể gọi LLM để route
```

Điều này giúp giảm độ trễ đáng kể.

## 7. Local LLM đang được dùng như thế nào

File:

```txt
app/llm/local_llm.py
```

### 7.1. Cơ chế load model

LocalLLM hiện:

```txt
1. đọc model path từ .env
2. dùng llama-cpp-python để load GGUF
3. cache model theo path trong _shared_models
4. tái sử dụng model giữa các request
```

### 7.2. Cơ chế chống crash

Do `llama-cpp-python` đã từng crash khi nhiều request generate cùng lúc,
hệ thống đang dùng một `infer lock`:

```txt
_infer_lock
```

Tức là:

```txt
Các lượt generate của local LLM hiện chạy tuần tự, không chạy song song.
```

### 7.3. Auto prompt format

Biến môi trường:

```txt
LLM_PROMPT_FORMAT=auto
```

Code sẽ tự chọn prompt format theo tên model path:

```txt
Qwen / VinaLLaMA → chatml
Llama 3.x        → llama3
```

## 8. ProductRepository làm gì

File:

```txt
app/products/product_repository.py
```

Đây là nơi quan trọng nhất cho dữ liệu thật.

### 8.1. Collections đang được dùng

Repository hiện query các collection sau:

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
```

### 8.2. Cách xác định product thuộc nhóm cây

Repository không hardcode category id.

Nó tìm category cây bằng:

```txt
name ~ "Plants" / "cây" / "cay"
slug ~ "plants" / "plant" / "cay"
```

Sau đó lấy luôn cả category con nếu có.

Khi query product, repository luôn cố ép điều kiện:

```txt
is_active != false
AND
(product_type == 'plant' OR category_id thuộc nhóm Plants)
```

### 8.3. Cách tìm sản phẩm

`get_product_by_name(query)` hiện search theo thứ tự:

```txt
products.name
products.slug
products.sku
```

Nếu không tìm được, repository fallback sang `plants`:

```txt
plants.scientific_name
plants.scientific_name_search
plants.common_name
```

Nếu tìm được plant thì lấy product có `products.plant_id` trỏ sang plant đó.

### 8.4. Cách build full product context

`get_product_full_context(product)` tạo context bằng cách join:

```txt
product
→ category bằng products.category_id
→ plant bằng products.plant_id
→ variants bằng product_variants.product_id = products._id
→ inventories bằng variant_inventory.variant_id in variants._id
→ images bằng product_images.product_id hoặc variant_id
```

Sau đó compute thêm:

```txt
price_min
price_max
price_text
available_qty
has_inventory
in_stock
variant_count
primary_image_url
```

### 8.5. Dữ liệu nào là nguồn sự thật

```txt
Giá      → product_variants.price
Tồn kho  → variant_inventory.available_qty
Độc tính → plants.toxicity_warning / plants.safety_notes
Ảnh      → product_images.image_url
```

## 9. Product Info flow hiện tại

File handler:

```txt
app/products/product_handler.py
```

### 9.1. Khi nào đi vào flow này

Các câu như:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây này còn hàng không?
Cây Jequirity bean có độc với mèo không?
```

thường vào `product_info`.

### 9.2. Các bước xử lý

```txt
1. lấy product_name từ route.entities nếu có
2. gọi repository.get_product_by_name(product_name)
3. nếu không thấy thì gọi repository.find_product_mentioned(message)
4. nếu vẫn không thấy thì trả message hỏi lại tên cây
5. nếu thấy product thì gọi repository.get_product_full_context(product)
6. build câu trả lời deterministic từ context
7. build product card từ context
8. trả về response
```

### 9.3. Product Info hiện có dùng LLM không

Hiện tại:

```txt
Không.
```

Lý do:

```txt
LLM local hiện đang CPU-only nên rất chậm cho factual flow.
Product Info đang dùng deterministic response để đảm bảo nhanh và đúng dữ liệu thật.
```

### 9.4. Câu trả lời được build thế nào

Handler sẽ nói dựa trên:

```txt
Tên sản phẩm
Giá từ computed.price_text
Tên variant hiện có
Tổng tồn kho từ computed.available_qty
Lưu ý an toàn nếu plant có toxicity_warning hoặc safety_notes
```

### 9.5. Ví dụ thực tế

Input:

```txt
Cây Aloe vera bao nhiêu tiền và còn hàng không?
```

Flow thật:

```txt
Router → product_info
→ products tìm Aloe vera
→ product_variants lấy giá 16.8
→ variant_inventory lấy available_qty = 23
→ build response deterministic
```

Kết quả hiện tại:

```txt
Aloe vera (Aloe barbadensis) hiện có giá 16,80. Các lựa chọn hiện có: Default. Tổng tồn kho có thể bán: 23.
```

## 10. Recommendation flow hiện tại

File handler:

```txt
app/recommendations/recommendation_handler.py
```

### 10.1. Khi nào đi vào flow này

Các câu như:

```txt
Tôi muốn cây dễ chăm dưới 300k.
Tôi muốn cây để bàn.
Tôi muốn cây hợp người mới chơi.
```

thường vào `recommendation`.

### 10.2. Các bước xử lý

```txt
1. lấy filters từ route.entities
2. bỏ product_name nếu router có extract nhầm
3. gọi repository.search_products(filters)
4. nếu ít candidate hoặc câu có tính semantic → dùng vector search
5. hydrate các vector result thành full product context
6. lọc lại context theo hard filters
7. merge kết quả hard-filter và vector-search
8. rank theo score
9. lấy top 3
10. build câu trả lời deterministic
11. build product cards
12. trả response
```

### 10.3. Hard filters hiện có

Recommendation hiện chỉ hard filter trên các field có thật:

```txt
care_level  → products.care_level
max_price   → computed.price_min, thực chất lấy từ product_variants.price
in_stock    → computed.in_stock, thực chất lấy từ variant_inventory.available_qty
```

### 10.4. Semantic/vector triggers

Nếu message chứa các từ như:

```txt
chill
sang
dep
quà
minimal
hiện đại
ít nắng
thiếu sáng
để bàn
phòng ngủ
phòng khách
hay quên tưới
```

thì handler ưu tiên bật vector search.

### 10.5. Recommendation hiện có dùng LLM không

Hiện tại:

```txt
Không.
```

Lý do giống Product Info:

```txt
LLM local CPU-only làm recommendation chậm đáng kể.
Handler đang trả deterministic answer để giữ tốc độ.
```

### 10.6. Ranking hiện tại

Score được cộng theo:

```txt
in_stock                    +1.0
care_level match            +1.3
price_min <= max_price      +1.2
rating_avg bonus            + nhỏ
vector_score                + theo semantic result
```

### 10.7. Ví dụ thực tế

Input:

```txt
Tôi muốn cây dễ chăm dưới 300k
```

Flow hiện tại:

```txt
Router → recommendation
entities = {max_price: 300000, care_level: easy}
→ repository.search_products(filters)
→ tìm products có care_level ~ Easy
→ hydrate variants/inventory/images/plants
→ rank
→ trả top 3 deterministic
```

Lưu ý quan trọng về dữ liệu thực tế:

```txt
DB hiện đang có giá kiểu 16.8, 39.9, 11.6 ...
Trong khi parser max_price kiểu "300k" → 300000.
Vì vậy gần như mọi sản phẩm hiện tại đều pass điều kiện ngân sách này.
```

## 11. Plant Care flow hiện tại

File handler:

```txt
app/knowledge/rag_handler.py
```

### 11.1. Khi nào đi vào flow này

Các câu như:

```txt
Tại sao lá cây bị vàng?
Cây bị úng rễ thì xử lý sao?
Cây tưới bao lâu một lần?
```

### 11.2. Các bước xử lý

```txt
1. embed câu hỏi bằng EmbeddingService
2. query vector search trên knowledge_chunks
3. nếu có chunk → build context + sources
4. nếu local LLM available → generate câu trả lời từ context
5. nếu không → fallback bằng cắt context đầu tiên
```

### 11.3. Nếu không có knowledge base

Handler trả:

```txt
Mình chưa có đủ thông tin trong tài liệu hiện tại.
```

### 11.4. Trạng thái hiện tại

Hiện DB thật bạn cho mình kiểm tra không có `knowledge_chunks` trong sample collections đang dùng cho shop,
nên flow này nhiều khả năng chưa phải flow chính ở giai đoạn hiện tại.

## 12. Cart Order flow hiện tại

`cart_order` hiện chỉ là placeholder.

Nếu router phát hiện ý định mua/giỏ hàng, ChatService trả:

```txt
Mình đã hiểu bạn muốn thao tác giỏ hàng/đặt hàng. Phần này nên nối với Cart API riêng...
```

Tức là:

```txt
Chưa có logic thêm giỏ thật trong chat flow hiện tại.
```

## 13. General flow hiện tại

### 13.1. Khi nào đi vào flow này

Ví dụ:

```txt
Xin chào
Bạn có thể giúp gì cho BigPlant?
```

### 13.2. Các bước xử lý

```txt
1. Router classify general
2. ChatService gọi self.llm.generate(GENERAL_PROMPT)
3. local LLM sinh câu trả lời ngắn
4. trả response
```

### 13.3. General hiện có dùng LLM không

```txt
Có.
```

Đây là flow chính hiện vẫn dùng local LLM trực tiếp.

## 14. Performance thực tế hiện tại

### 14.1. Vì sao trước đây rất chậm

Nguyên nhân chính:

```txt
1. llama-cpp-python hiện đang CPU-only
2. supports_gpu_offload = False
3. factual flow trước đây còn gọi LLM để diễn giải JSON dài
4. nhiều request đồng thời từng làm model crash / segmentation fault
```

### 14.2. Tối ưu đã áp dụng

```txt
ChatService được cache singleton
LocalLLM cache model theo model path
LocalLLM có infer lock để tránh concurrent crash
Router chỉ gọi LLM nếu intent heuristic là unclear
Product Info không dùng LLM
Recommendation không dùng LLM
General vẫn dùng LLM
```

### 14.3. Kết quả timing thực tế

Sau khi tối ưu, timing điển hình:

```txt
product_info     ~ 1.5 giây
recommendation   ~ 3-4 giây
general          ~ 7 giây
```

General chậm hơn vì còn chạy local LLM thật trên CPU.

## 15. Query thật đang chạm collection nào theo từng flow

### Product Info

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
```

### Recommendation

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
vector index trên products nếu bật semantic search
```

### Plant Care

```txt
knowledge_chunks
knowledge vector index
```

### General

```txt
Không query MongoDB nghiệp vụ
Chỉ gọi local LLM
```

## 16. Tóm tắt “một câu hỏi đi như thế nào”

### Case A: hỏi giá/tồn kho/sản phẩm cụ thể

```txt
User hỏi
→ router thấy marker giá/tồn kho/độc tính/size
→ intent = product_info
→ query products
→ join variants + inventory + images + plants
→ build deterministic answer
→ trả text + product card
```

### Case B: hỏi tư vấn chọn cây

```txt
User hỏi
→ router thấy marker tư vấn/chọn cây
→ intent = recommendation
→ extract filters
→ search products theo hard filters
→ nếu semantic thì vector search
→ hydrate full contexts
→ rank top 3
→ build deterministic answer
→ trả text + product cards
```

### Case C: hỏi kiến thức chăm cây

```txt
User hỏi
→ router thấy marker vàng lá/úng rễ/chăm sóc
→ intent = plant_care
→ embed query
→ vector search knowledge_chunks
→ nếu có context thì dùng LLM trả lời
→ nếu không thì báo chưa đủ tài liệu
```

### Case D: chào hỏi/trò chuyện chung

```txt
User hỏi
→ router thấy marker general
→ intent = general
→ local LLM generate câu trả lời
→ trả text
```

### Case E: quá mơ hồ

```txt
User hỏi
→ heuristic không rõ
→ intent = unclear
→ router có thể gọi local LLM để phân loại JSON
→ nếu vẫn unclear thì trả câu hỏi gợi mở cho user
```

## 17. Điểm quan trọng để đưa vào slide

Nếu bạn cần slide ngắn gọn, có thể nhấn mạnh 7 ý sau:

```txt
1. Chatbot không đẩy mọi câu hỏi vào LLM.
2. Request được route theo intent trước.
3. Product Info dùng MongoDB thật, không cho LLM bịa.
4. Recommendation dùng hard filters + vector search.
5. Plant Care dùng RAG nếu có knowledge base.
6. General chat mới là nơi local LLM trả lời trực tiếp.
7. Timing và metadata được ghi lại để debug hiệu năng.
```
