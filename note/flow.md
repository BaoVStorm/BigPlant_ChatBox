# BigPlant App Flow

File này mô tả **flow thực thi thật của source code hiện tại**. Mục tiêu là giải thích rõ: khi user hỏi một câu, hệ thống sẽ đi qua những bước nào, router nhận diện intent ra sao, mỗi intent xử lý như thế nào, query collection nào, và model nào được dùng ở từng bước.

Nội dung ở đây chỉ tập trung vào **logic của app hiện tại**.

## 1. Mục tiêu của flow

App không dùng một prompt LLM duy nhất cho tất cả câu hỏi. Thay vào đó, app làm theo logic sau:

```txt
1. Nhận câu hỏi của user
2. Router xác định intent
3. Mỗi intent đi vào một nhánh xử lý riêng
4. MongoDB là nguồn dữ liệu thật cho giá, tồn kho, ảnh, độc tính
5. LLM chỉ dùng ở những nơi phù hợp
```

Ý nghĩa của cách làm này:

```txt
- giảm hallucination
- tăng tốc độ ở các câu factual
- dễ kiểm soát hơn
- dễ debug hơn
- dễ mở rộng theo từng flow nghiệp vụ
```

## 2. Entry point của app

API chính của chatbot:

```txt
POST /api/chat/message
```

File route:

```txt
app/chat/chat_router.py
```

Payload đầu vào:

```txt
message
user_id
session_id
```

Response đầu ra:

```txt
intent
message
products
sources
metadata
```

## 3. Luồng tổng quát khi user hỏi một câu

Khi user gửi một câu hỏi, luồng chạy như sau:

```txt
User question
→ FastAPI route nhận request
→ ChatService singleton xử lý
→ IntentRouter classify câu hỏi
→ ChatService chọn handler theo intent
→ Handler query MongoDB hoặc dùng LLM tùy flow
→ Build response JSON
→ Trả về cho user
```

Trong code, file điều phối chính là:

```txt
app/chat/chat_service.py
```

`ChatService.handle_message(...)` làm 4 việc lớn:

```txt
1. đo thời gian xử lý
2. gọi router để phân loại intent
3. dispatch sang handler tương ứng
4. gắn metadata.timing_ms vào response
```

## 4. Các thành phần chính trong source code

```txt
app/chat/chat_router.py
  → endpoint /api/chat/message

app/chat/chat_service.py
  → điều phối flow theo intent

app/router/intent_router.py
  → nhận diện intent + extract entities

app/products/product_repository.py
  → query MongoDB, join dữ liệu product/category/plant/variant/inventory/image

app/products/product_handler.py
  → xử lý Product Info

app/recommendations/recommendation_handler.py
  → xử lý Recommendation

app/knowledge/rag_handler.py
  → xử lý Plant Care / RAG

app/llm/local_llm.py
  → load local LLM, generate text, generate JSON

app/embeddings/embedding_service.py
  → load local embedding model, embed query/example/product
```

## 5. Router hoạt động như thế nào

File:

```txt
app/router/intent_router.py
```

Router hiện tại được thiết kế theo **3 tầng**:

```txt
Tầng 1: weighted rules
Tầng 2: semantic intent examples
Tầng 3: local LLM fallback only when uncertain
```

Đây là phần quan trọng nhất của flow.

---

## 6. Trước khi classify: normalize + extract entities

### 6.1. Normalize text

Trước khi chấm intent, router normalize câu hỏi:

```txt
1. lower-case
2. bỏ dấu tiếng Việt
3. co khoảng trắng
```

Ví dụ:

```txt
"Cây có độc với mèo không?"
→ "cay co doc voi meo khong?"
```

Mục đích:

```txt
- giúp rule ổn định hơn
- giảm phụ thuộc vào dấu tiếng Việt
- giúp cùng một marker match được nhiều cách gõ
```

### 6.2. Extract entities trước khi xác định intent

Router không chỉ đo intent, mà còn rút ra entity để dùng cho handler sau này.

Entity hiện đang extract:

```txt
product_name
max_price
budget_input_currency
budget_input_amount
budget_catalog_currency
care_level
watering_need
light_requirement
placement
pet_safe
```

Ý nghĩa từng entity:

```txt
product_name
  → tên cây/sản phẩm cụ thể nếu câu hỏi có nhắc

max_price
  → ngân sách đã normalize về cùng đơn vị với catalog price

budget_input_currency
  → tiền tệ user nhập vào, ví dụ VND hoặc USD

budget_input_amount
  → số tiền gốc user nói

budget_catalog_currency
  → currency mà hệ thống đang dùng để so với product price

care_level
  → ví dụ easy khi có các cụm như dễ chăm, người mới, ít chăm

watering_need
  → ví dụ low khi có các cụm như hay quên tưới, ít tưới

light_requirement
  → ví dụ low nếu có cụm ít nắng, thiếu sáng

placement
  → desk / office / bedroom / living_room nếu câu có nhắc không gian đặt cây

pet_safe
  → gắn true nếu câu liên quan mèo/chó/thú cưng
```

### 6.3. Parse ngân sách theo currency

Router hiện có logic parse ngân sách từ nhiều dạng khác nhau:

```txt
dưới 300k
dưới 1 triệu
$20
20 USD
```

Sau khi parse, router convert về currency mà catalog đang dùng.

Ví dụ nếu catalog đang dùng USD:

```txt
400K VND → khoảng 16 USD
$20      → 20 USD
```

Mục tiêu:

```txt
tránh việc 400K và $20 bị hiểu như cùng một mức giá
```

---

## 7. Tầng 1: weighted rules

Đây là tầng đầu tiên của router.

### 7.1. Mục tiêu của tầng rules

Tầng này dùng để bắt nhanh những câu hỏi có ý định rất rõ.

Ví dụ:

```txt
"thêm vào giỏ"
"bao nhiêu tiền"
"còn hàng không"
"tư vấn cây dễ chăm"
"tại sao lá cây bị vàng"
```

### 7.2. Cách hoạt động

Mỗi intent có một tập pattern + trọng số.

Ví dụ ý tưởng:

```txt
cart_order:
  "them vao gio"  → điểm cao
  "mua ngay"      → điểm cao

product_info:
  "bao nhieu tien" → điểm cao
  "con hang"       → điểm cao
  "co doc"         → điểm cao

recommendation:
  "tu van"         → điểm cao
  "goi y"          → điểm cao
  "de ban"         → điểm vừa

plant_care:
  "vang la"        → điểm cao
  "ung re"         → điểm cao

general:
  "xin chao"       → điểm cao
  "cam on"         → điểm cao
```

Sau khi match rules:

```txt
1. tính tổng điểm từng intent
2. lấy intent có điểm cao nhất
3. so sánh với intent đứng thứ hai
4. nếu score đủ mạnh và margin đủ xa thì return luôn
5. nếu chưa đủ chắc thì chuyển sang semantic layer
```

### 7.3. Tầng này để làm gì

```txt
- nhanh
- rẻ
- không cần gọi embedding/LLM nếu câu quá rõ
- đặc biệt tốt cho cart, product info cơ bản, greeting
```

### 7.4. Khi nào rules kết thúc flow router

Rules sẽ chốt luôn nếu:

```txt
best_score đủ cao
AND
best_score cách xa second_score đủ lớn
```

Nếu không đạt điều kiện này, router chưa tin hoàn toàn, nên sẽ sang semantic layer.

---

## 8. Tầng 2: semantic intent examples

Đây là tầng giúp app hiểu các câu **gần nghĩa**, không cần trùng đúng marker.

### 8.1. Mục tiêu của semantic layer

Giải quyết vấn đề mà rules không làm tốt:

```txt
user không gõ đúng marker
user paraphrase câu hỏi
user dùng cách nói tự nhiên hơn
```

Ví dụ:

```txt
"shop còn mẫu này không"
"mình cần cây cho góc làm việc"
"lá cây bị úng thì cứu sao"
"alo bạn ơi"
```

### 8.2. Cách hoạt động

Router có một tập câu mẫu cho từng intent.

Ví dụ:

```txt
product_info:
  Cây monstera bao nhiêu tiền
  Cây này còn hàng không
  Shop còn mẫu này không

recommendation:
  Tôi muốn cây dễ chăm cho người mới
  Phòng tôi ít nắng nên chọn cây gì
  Mình muốn tìm một cây tặng sinh nhật

plant_care:
  Tại sao lá cây bị vàng
  Cây bị úng rễ xử lý sao

cart_order:
  Thêm cây này vào giỏ hàng
  Mua ngay sản phẩm này

general:
  Xin chào
  Alo bạn ơi
```

Flow semantic:

```txt
1. embed câu user bằng embedding model
2. embed toàn bộ câu mẫu intent
3. tính similarity giữa câu user và từng câu mẫu
4. lấy similarity cao nhất cho mỗi intent
5. cộng nhẹ rule score vào semantic score nếu có
6. chọn intent có điểm semantic tốt nhất
7. nếu score đủ cao và margin đủ ổn thì return
8. nếu vẫn chưa chắc thì mới sang LLM fallback
```

### 8.3. Tầng này để làm gì

```txt
- bắt câu gần nghĩa tốt hơn rules
- không cần user gõ đúng marker
- giảm số lần phải gọi local LLM
- tăng độ chính xác cho tiếng Việt tự nhiên
```

### 8.4. Embedding model nào đang dùng ở tầng này

Model embedding hiện tại:

```txt
BAAI/bge-m3
```

Và được load bởi:

```txt
app/embeddings/embedding_service.py
```

Embedding model này hiện được dùng ở 3 chỗ trong app:

```txt
1. semantic intent router
2. product recommendation vector search
3. plant care / RAG vector search
```

---

## 9. Tầng 3: local LLM fallback

Đây là tầng cuối cùng của router.

### 9.1. Khi nào mới dùng tầng này

Chỉ dùng nếu:

```txt
rules chưa đủ chắc
AND semantic chưa đủ chắc
AND local LLM available
```

Tức là local LLM **không** bị gọi ở mọi request.

### 9.2. Cách hoạt động

Router build prompt JSON classifier:

```txt
Bạn là intent router...
Hãy phân loại câu hỏi vào product_info / recommendation / plant_care / cart_order / general / unclear
Chỉ trả JSON
```

Sau đó parse JSON từ model.

### 9.3. Tầng này để làm gì

```txt
- xử lý câu quá mơ hồ
- xử lý trường hợp rules và semantic không đủ tự tin
- giữ app linh hoạt mà không phải gọi LLM cho mọi câu
```

---

## 10. Tóm tắt logic quyết định intent

Một câu hỏi đi qua router như sau:

```txt
Input user message
→ normalize
→ extract entities
→ weighted rules scoring
→ nếu rules đủ mạnh: return intent
→ nếu chưa đủ: semantic examples scoring
→ nếu semantic đủ mạnh: return intent
→ nếu vẫn chưa đủ: local LLM fallback
→ nếu LLM fail: fallback về semantic hoặc rules tốt nhất hiện có
```

Đây là flow nhận diện intent hiện tại của app.

## 11. Các intent hiện có và từng intent làm gì

App hiện có 6 intent:

```txt
product_info
recommendation
plant_care
cart_order
general
unclear
```

---

## 12. Intent: product_info

### 12.1. Dùng khi nào

Intent này dùng khi user hỏi về **một sản phẩm cây cụ thể**.

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây này còn hàng không?
Cho mình xem thông tin cây aloe vera
Cây Jequirity bean có độc với mèo không?
```

### 12.2. Detect như thế nào

Rules bắt tốt các từ như:

```txt
bao nhieu tien
gia
con hang
ton kho
size
hinh anh
co doc
an toan cho thu cung
thong tin
```

Semantic layer giúp bắt các câu gần nghĩa như:

```txt
shop còn mẫu này không
cho mình xem thông tin cây aloe vera
```

### 12.3. Flow xử lý sau khi detect được

Handler:

```txt
app/products/product_handler.py
```

Flow chi tiết:

```txt
1. lấy product_name từ route.entities nếu có
2. gọi ProductRepository.get_product_by_name(product_name)
3. nếu chưa thấy thì gọi ProductRepository.find_product_mentioned(message)
4. nếu vẫn chưa thấy thì trả câu hỏi yêu cầu user nêu tên cây cụ thể
5. nếu thấy product thì gọi get_product_full_context(product)
6. repository join dữ liệu thật:
   - products
   - product_categories
   - plants
   - product_variants
   - variant_inventory
   - product_images
7. repository compute:
   - price_min
   - price_max
   - price_text
   - available_qty
   - in_stock
   - primary_image_url
8. ProductInfoHandler build câu trả lời deterministic
9. build product card
10. trả response
```

### 12.4. Nguồn dữ liệu thật ở intent này

```txt
products                    → tên sản phẩm, slug, sku, mô tả, care_level
product_variants            → giá thật, variant name, attributes
variant_inventory           → tồn kho thật
product_images              → ảnh
plants                      → độc tính, safety notes, mô tả cây nền
product_categories          → category Plants/Pots
```

### 12.5. Có dùng LLM không

Hiện tại:

```txt
Không dùng LLM để trả lời product_info.
```

Lý do:

```txt
flow này cần factual correctness cao
MongoDB đã đủ dữ liệu để build deterministic answer
tránh chậm và tránh hallucination
```

---

## 13. Intent: recommendation

### 13.1. Dùng khi nào

Intent này dùng khi user muốn được tư vấn chọn cây theo nhu cầu.

Ví dụ:

```txt
Tôi muốn cây dễ chăm dưới 400K
Mình cần cây cho góc làm việc
Phòng tôi ít nắng nên chọn cây gì
Tôi muốn cây làm quà tặng sinh nhật
```

### 13.2. Detect như thế nào

Rules bắt các từ như:

```txt
tu van
goi y
nen mua
nen chon
chon cay
phu hop
de ban
phong khach
phong ngu
van phong
```

Semantic layer bắt các câu gần nghĩa như:

```txt
mình cần cây cho góc làm việc
mình muốn tìm một cây tặng sinh nhật
```

### 13.3. Flow xử lý sau khi detect được

Handler:

```txt
app/recommendations/recommendation_handler.py
```

Flow chi tiết:

```txt
1. lấy filters từ route.entities
2. bỏ product_name nếu router extract nhầm vào recommendation
3. gọi ProductRepository.search_products(filters)
4. repository filter theo dữ liệu có thật:
   - is_active
   - product_type='plant' hoặc category Plants
   - care_level nếu có
   - max_price sau khi normalize currency
   - in_stock nếu có
5. search_products hydrate full product context cho từng candidate
6. nếu candidate ít hoặc query có tính semantic → bật vector search
7. vector search lấy product id theo embedding
8. hydrate lại vector result thành full product context
9. merge hard-filter result + vector result
10. rank candidates
11. lấy top 3
12. build deterministic answer
13. build product cards
14. trả response
```

### 13.4. Nguồn dữ liệu thật ở intent này

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
vector index trên products
```

### 13.5. Recommendation có dùng embedding không

```txt
Có.
```

Embedding được dùng khi query có yếu tố semantic hoặc hard filter chưa đủ.

### 13.6. Recommendation có dùng LLM để trả lời không

Hiện tại:

```txt
Không.
```

Handler đang build deterministic answer để giữ tốc độ và độ ổn định.

### 13.7. Hard filter nào đang được áp dụng thật

Hiện tại recommendation chỉ filter cứng trên các field có thật:

```txt
care_level  → products.care_level
max_price   → computed.price_min, thực chất lấy từ product_variants.price
in_stock    → computed.in_stock, thực chất lấy từ variant_inventory.available_qty
```

### 13.8. Semantic recommendation để làm gì

Semantic/vector search được dùng cho các nhu cầu như:

```txt
để bàn
ít nắng
thiếu sáng
phòng ngủ
phòng khách
quà tặng
minimal
chill
```

Vì DB hiện tại chưa có field cứng hoàn chỉnh cho các nhu cầu này.

---

## 14. Intent: plant_care

### 14.1. Dùng khi nào

Intent này dùng cho câu hỏi kiến thức chăm cây.

Ví dụ:

```txt
Tại sao lá cây bị vàng?
Lá cây bị úng thì cứu sao?
Cây tưới bao lâu một lần?
```

### 14.2. Detect như thế nào

Rules bắt các từ như:

```txt
vang la
ung re
thoi re
heo la
dom la
sau benh
tuoi bao lau
cham soc
```

Semantic layer bắt các câu gần nghĩa như:

```txt
lá cây bị úng thì cứu sao
cách cứu cây sắp chết
```

### 14.3. Flow xử lý sau khi detect được

Handler:

```txt
app/knowledge/rag_handler.py
```

Flow chi tiết:

```txt
1. embed câu hỏi user bằng EmbeddingService
2. query vector search trên knowledge_chunks
3. nếu có chunks:
   - build context
   - build sources
   - nếu local LLM available thì generate câu trả lời từ context
   - nếu LLM fail thì fallback bằng cắt nội dung chunk đầu tiên
4. nếu không có chunks thì trả message chưa có đủ tài liệu
```

### 14.4. Nguồn dữ liệu thật ở intent này

```txt
knowledge_chunks
knowledge vector index
```

### 14.5. Có dùng embedding không

```txt
Có.
```

### 14.6. Có dùng LLM không

```txt
Có, nhưng chỉ sau khi đã có context từ knowledge base.
```

---

## 15. Intent: cart_order

### 15.1. Dùng khi nào

Ví dụ:

```txt
Thêm sản phẩm này vào giỏ
Mua ngay cây này
Đặt hàng giúp mình
```

### 15.2. Detect như thế nào

Rules bắt các từ như:

```txt
them vao gio
gio hang
dat hang
mua ngay
checkout
thanh toan
```

Semantic layer bắt các câu gần nghĩa như:

```txt
thêm sản phẩm này vào giỏ giúp mình
```

### 15.3. Flow xử lý sau khi detect được

Hiện tại flow này **chưa nối Cart API thật**.

ChatService trả placeholder:

```txt
Mình đã hiểu bạn muốn thao tác giỏ hàng/đặt hàng. Phần này nên nối với Cart API riêng...
```

Tức là:

```txt
intent được nhận diện đúng
nhưng chưa có side effect thêm giỏ hàng thật
```

---

## 16. Intent: general

### 16.1. Dùng khi nào

Ví dụ:

```txt
Xin chào
Alo bạn ơi
Bạn có thể giúp gì cho BigPlant?
```

### 16.2. Detect như thế nào

Rules bắt các từ như:

```txt
xin chao
hello
hi
cam on
```

Semantic layer bắt các câu gần nghĩa như:

```txt
alo bạn ơi
giúp mình với
```

### 16.3. Flow xử lý sau khi detect được

Flow general có 2 nhánh nhỏ:

#### Nhánh A: greeting ngắn

Nếu câu là greeting ngắn như:

```txt
xin chào
alo bạn ơi
hello
```

thì `ChatService._handle_general(...)` trả deterministic greeting,
không gọi LLM.

Mục đích:

```txt
- nhanh hơn
- tránh model sinh text rác
- tránh lãng phí tài nguyên
```

#### Nhánh B: general chat dài hơn

Nếu không phải greeting ngắn, flow là:

```txt
1. ChatService gọi self.llm.generate(GENERAL_PROMPT)
2. local LLM sinh câu trả lời ngắn
3. nếu LLM fail → fallback bằng static answer
```

### 16.4. Có dùng LLM không

```txt
Có, nhưng không phải mọi general message đều dùng.
Greeting ngắn thì deterministic, câu general dài hơn mới dùng local LLM.
```

---

## 17. Intent: unclear

### 17.1. Khi nào xảy ra

Khi:

```txt
rules không chắc
semantic không chắc
LLM fallback cũng không đưa ra intent đủ tin cậy
```

### 17.2. App làm gì

App trả câu hỏi gợi mở:

```txt
Bạn muốn hỏi thông tin cây cụ thể, nhờ mình tư vấn chọn cây, hay hỏi cách chăm cây?
```

Mục đích:

```txt
buộc user làm rõ ý định thay vì để app đoán sai
```

## 18. Full flow của một câu hỏi trong app

Đây là flow end-to-end đúng với source code hiện tại.

### Bước 1: API nhận request

```txt
POST /api/chat/message
payload: { message, user_id, session_id }
```

### Bước 2: ChatService nhận message

```txt
handle_message(message, user_id, session_id)
```

### Bước 3: Router classify

```txt
normalize text
→ extract entities
→ rules scoring
→ nếu đủ chắc thì return
→ nếu chưa đủ thì semantic scoring
→ nếu đủ chắc thì return
→ nếu chưa đủ thì LLM fallback
```

### Bước 4: Switch theo intent

```txt
product_info   → ProductInfoHandler
recommendation → RecommendationHandler
plant_care     → PlantCareRagHandler
cart_order     → placeholder branch
general        → general branch
unclear        → fallback branch
```

### Bước 5: Handler xử lý nghiệp vụ

```txt
query MongoDB / vector search / local LLM tùy flow
```

### Bước 6: Build response

```txt
message
products
sources
metadata.route
metadata.timing_ms
```

### Bước 7: Trả JSON cho frontend

```txt
Frontend nhận response và render chat text + product cards nếu có.
```

## 19. Model nào đang dùng trong app

App hiện có 2 loại model chính:

```txt
1. Local LLM
2. Embedding model
```

### 19.1. Local LLM mặc định đang dùng

Model mặc định trong `.env` hiện là:

```txt
Qwen2.5-7B-Instruct Q4_K_M
```

Vai trò trong app:

```txt
router fallback khi rules + semantic chưa chắc
general chat
plant care nếu đã có context RAG
```

### 19.2. 3 lựa chọn LLM đang có trong app

#### Qwen2.5-7B-Instruct Q4_K_M

Vai trò:

```txt
model mặc định hiện tại
```

Điểm mạnh:

```txt
tiếng Việt ổn
instruction following tốt
chat tự nhiên hơn VinaLLaMA
phù hợp làm model mặc định cho app
```

Điểm yếu:

```txt
nếu chạy CPU-only thì vẫn chậm
```

#### Meta-Llama-3.1-8B-Instruct Q4_K_M

Vai trò:

```txt
model thay thế để benchmark chất lượng general/reasoning
```

Điểm mạnh:

```txt
general chat tốt
reasoning tốt
ổn định khi viết câu trả lời tự nhiên
```

Điểm yếu:

```txt
tiếng Việt không đều bằng Qwen trong một số câu tự nhiên
```

#### VinaLLaMA-7B-Chat Q5_0

Vai trò:

```txt
model thay thế thiên tiếng Việt
```

Điểm mạnh:

```txt
hợp để test hội thoại tiếng Việt
```

Điểm yếu:

```txt
cũ hơn
reasoning yếu hơn Qwen/Llama 3.1
tuân thủ instruction không tốt bằng Qwen
```

## 20. Embedding model đang dùng

Model embedding hiện tại:

```txt
BAAI/bge-m3
```

Vai trò trong app:

```txt
1. semantic intent router
2. product recommendation vector search
3. plant care / RAG vector search
```

### 20.1. Flow của embedding trong app

#### A. Semantic router

```txt
message
→ embed query
→ so với intent example vectors
→ lấy intent semantic gần nhất
```

#### B. Recommendation vector search

```txt
message recommendation có tính semantic
→ embed query
→ search product vector index
→ lấy danh sách product gần nghĩa
→ hydrate lại từ MongoDB
→ rank
```

#### C. Plant care RAG

```txt
message plant care
→ embed query
→ search knowledge_chunks vector index
→ lấy top chunks
→ build context
→ đưa context cho local LLM
```

## 21. Điểm quan trọng nhất của logic app hiện tại

Nếu cần tóm gọn phần logic để thuyết trình, có thể chốt bằng 8 ý sau:

```txt
1. App không đẩy mọi câu hỏi vào LLM.
2. App route câu hỏi trước, rồi mới xử lý theo intent.
3. Router hiện là 3 tầng: rules → semantic → LLM fallback.
4. Product Info dùng MongoDB thật, không cho LLM bịa.
5. Recommendation dùng hard filters + vector search.
6. Plant Care dùng embedding + RAG nếu có knowledge base.
7. General chat mới là nơi local LLM được dùng trực tiếp nhiều hơn.
8. Mọi response đều đi qua metadata.timing_ms để debug hiệu năng.
```
