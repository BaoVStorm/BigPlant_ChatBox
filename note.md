## Hybrid chatbot hoàn chỉnh nên thiết kế theo hướng:

```
MongoDB/API = nguồn dữ liệu thật
LLM = hiểu câu hỏi + diễn giải
Vector Search = tìm kiếm theo ý nghĩa
RAG = trả lời kiến thức chăm cây
Router = quyết định câu hỏi đi theo nhánh nào
```

## Kiến trúc tổng thể:

```
User
 ↓
Chat UI
 ↓
Chat Backend API
 ↓
Intent Router
 ├── Product Info       → MongoDB
 ├── Recommendation     → MongoDB Filter + Vector Search
 ├── Plant Care Q&A     → RAG / Knowledge Base
 └── General Chat       → LLM
 ↓
LLM Response Generator
 ↓
User
```

# II. Chia chatbot thành các nhóm chức năng

Không nên làm một chatbot “hỏi gì cũng ném vào LLM”. Nên chia thành các intent rõ ràng.

## Nhóm 1: Product Info

Dùng cho câu hỏi về sản phẩm cụ thể.

Ví dụ:

```
Cây Monstera bao nhiêu tiền?
Cây lưỡi hổ còn hàng không?
Cây này có mấy size?
Cây trầu bà có độc với mèo không?
```

Nguồn dữ liệu:

```
MongoDB products
MongoDB variants
MongoDB inventory
MongoDB product_images
```

Không dùng LLM để tự đoán giá/tồn kho.

## Nhóm 2: Recommendation

Dùng cho tư vấn chọn cây.

Ví dụ:

```
Tôi muốn cây dễ chăm để bàn làm việc
Tôi hay quên tưới thì nên mua cây nào?
Phòng tôi ít nắng, nên chọn cây gì?
Tôi muốn cây nhìn sang cho phòng khách
```

Nguồn dữ liệu:

```
MongoDB filter
+
Vector search
```

Ví dụ:

```
giá dưới 300k          → MongoDB filter
dễ chăm                → MongoDB filter
ít nắng                → MongoDB filter
nhìn sang              → vector search
hợp người mới chơi     → vector search
```

## Nhóm 3: Plant Care Q&A

Dùng cho kiến thức chăm cây.

Ví dụ:

```
Tại sao lá Monstera bị vàng?
Cây lưỡi hổ tưới bao lâu một lần?
Cây bị úng rễ thì xử lý sao?
Có nên để cây trong phòng ngủ không?
```

Nguồn dữ liệu:

```
Plant care articles
FAQ
Care guide
Blog
Knowledge base
```

Hướng xử lý:

```
RAG = search tài liệu liên quan → đưa context cho LLM trả lời
```

# III. Thiết kế data trong MongoDB để chatbot dễ dùng

Nên chuẩn hóa products để chatbot query được tốt hơn. Đừng để mọi thứ chỉ nằm trong description.

Ví dụ: `collection products`:

```json
{
  _id: ObjectId,
  category_id: ObjectId,
  plant_id: ObjectId,

  sku: "MONSTERA-001",
  name: "Monstera Deliciosa",
  slug: "monstera-deliciosa",

  short_description: "Cây lá xẻ lớn, hợp phòng khách và văn phòng.",
  description: "Monstera Deliciosa là cây cảnh trong nhà...",

  price_min: 250000,
  price_max: 550000,

  care_level: "medium",
  light_requirement: "indirect",
  watering_need: "medium",
  humidity_need: "high",

  indoor_outdoor: "indoor",
  pet_safe: false,

  suitable_locations: [
    "living_room",
    "office",
    "balcony"
  ],

  suitable_for: [
    "home_decor",
    "office_decor",
    "plant_lovers"
  ],

  tags: [
    "tropical",
    "large_leaf",
    "decorative",
    "popular"
  ],

  care_guide: {
    watering: "Tưới khi mặt đất khô 2-3cm.",
    light: "Ưa ánh sáng gián tiếp.",
    soil: "Đất thoát nước tốt.",
    common_problems: [
      "yellow_leaves",
      "root_rot",
      "brown_edges"
    ]
  },

  is_active: true,
  created_at: Date,
  updated_at: Date
}
```

Collection `product_variants`:

```json
{
  _id: ObjectId,
  product_id: ObjectId,
  sku: "MONSTERA-SMALL",
  size: "small",
  pot_type: "plastic",
  price: 250000,
  stock: 12,
  is_active: true
}
```

Collection `plant_knowledge_articles`:

```json
{
  _id: ObjectId,
  title: "Cách xử lý cây bị vàng lá",
  slug: "cach-xu-ly-cay-bi-vang-la",
  content: "Lá cây bị vàng thường do tưới quá nhiều...",
  related_plants: ["monstera-deliciosa"],
  topics: ["yellow_leaves", "watering", "root_rot"],
  is_active: true,
  created_at: Date,
  updated_at: Date
}
```

# IV. Thiết kế các tool/function cho chatbot

LLM không nên tự query MongoDB trực tiếp. Nên expose các function an toàn.

## Product tools
```js
getProductByName(name: string)
getProductBySlug(slug: string)
searchProducts(filters)
getProductVariants(productId: string)
getProductInventory(productId: string)
getProductImages(productId: string)
```

## Recommendation tools
```js
recommendProductsByFilters(filters)
semanticSearchProducts(query, filters)
getSimilarProducts(productId)
```

## Knowledge tools
```js
searchPlantKnowledge(query)
getCareGuideByProduct(productId)
```

# V. Xây Intent Router trước

Đây là phần rất quan trọng.

- Router có nhiệm vụ phân loại câu hỏi:
```
product_info
recommendation
plant_care
general
unclear
```

- Ví dụ input/output:
```
User: Cây Monstera bao nhiêu tiền?
Intent: product_info
```
```
User: Tôi muốn cây dễ chăm để bàn làm việc
Intent: recommendation
```
```
User: Tại sao lá cây bị vàng?
Intent: plant_care
```
```
User: Thêm cây này vào giỏ hàng
Intent: cart_order
```

- Bạn có thể làm router bằng LLM với JSON output.

Ví dụ prompt:
```
Bạn là intent router cho app bán cây cảnh.

Hãy phân loại message của user vào một trong các intent:
- product_info
- recommendation
- plant_care
- cart_order
- general
- unclear

Chỉ trả JSON.

User message:
"Tôi muốn cây dễ chăm để bàn làm việc"
```

Output:
```
{
  "intent": "recommendation",
  "confidence": 0.92,
  "entities": {
    "care_level": "easy",
    "placement": "desk"
  }
}
```

# VI. Flow xử lý message chuẩn
Pseudo code tổng thể:
```js
async function handleChatMessage(userId: string, message: string) {
  const session = await getChatSession(userId);

  const route = await classifyIntent(message, session);

  switch (route.intent) {
    case "product_info":
      return await handleProductInfo(userId, message, route, session);

    case "recommendation":
      return await handleRecommendation(userId, message, route, session);

    case "plant_care":
      return await handlePlantCare(userId, message, route, session);

    case "cart_order":
      return await handleCartOrder(userId, message, route, session);

    case "general":
      return await handleGeneralChat(userId, message, session);

    default:
      return {
        message: "Bạn muốn hỏi về cây nào hoặc muốn mình tư vấn cây theo nhu cầu nào?"
      };
  }
}
```

# VII. Flow Product Info 

Ví dụ user hỏi:
```
Cây Monstera bao nhiêu tiền?
```
Flow:
```
1. Router detect product_info
2. Extract product_name = Monstera
3. Query MongoDB getProductByName("Monstera")
4. Query variants/inventory/images
5. Đưa dữ liệu thật cho LLM
6. LLM trả lời
```
Pseudo code:
```js
async function handleProductInfo(userId, message, route, session) {
  const productName = route.entities.product_name;

  if (!productName) {
    return {
      message: "Bạn muốn hỏi thông tin của cây nào?"
    };
  }

  const product = await getProductByName(productName);

  if (!product) {
    return {
      message: `Mình chưa tìm thấy cây "${productName}". Bạn có thể kiểm tra lại tên cây không?`
    };
  }

  const variants = await getProductVariants(product._id);
  const images = await getProductImages(product._id);

  return await generateAnswer({
    type: "product_info",
    userMessage: message,
    data: {
      product,
      variants,
      images
    }
  });
}
```

LLM prompt:
```
Bạn là chatbot tư vấn cây cảnh.
Chỉ được trả lời dựa trên dữ liệu product/variant được cung cấp.
Không tự bịa giá, tồn kho, size hoặc thông tin sản phẩm.

User hỏi:
{{message}}

Product data:
{{product_json}}

Variant data:
{{variant_json}}
```


## 7. Flow Recommendation

### 7.1. Mục tiêu

Flow Recommendation dùng để tư vấn cây phù hợp với nhu cầu của user.

Ví dụ user hỏi:

```text
Tôi muốn cây để bàn, ít nắng, dễ chăm, dưới 300k.
Tôi hay quên tưới thì nên mua cây nào?
Phòng tôi ít ánh sáng, nên chọn cây gì?
Tôi muốn cây nhìn sang cho phòng khách.
```

Flow này không nên để LLM tự bịa câu trả lời. LLM chỉ nên dùng để:

```text
1. Hiểu nhu cầu user.
2. Parse nhu cầu thành filter/query.
3. Diễn giải kết quả lấy từ database/vector search.
```

Dữ liệu sản phẩm thật vẫn phải lấy từ MongoDB.

---

### 7.2. Khi nào dùng Flow Recommendation?

Dùng khi user có ý định chọn/mua/tìm cây theo nhu cầu:

```text
- Cây dễ chăm
- Cây để bàn
- Cây hợp phòng ngủ
- Cây dưới 300k
- Cây ít cần tưới
- Cây hợp người mới chơi
- Cây chịu thiếu sáng
- Cây nhìn sang/trang trí đẹp
```

Không dùng flow này cho câu hỏi kiến thức bệnh cây/chăm cây chuyên sâu. Những câu đó nên đi qua **Plant Care RAG**.


### 7.4. Flow tổng quan

```text
User message
  ↓
Intent Router detect: recommendation
  ↓
Extract recommendation filters
  ↓
Query MongoDB bằng filter cứng
  ↓
Nếu kết quả đủ tốt
  ↓
Rank products
  ↓
LLM generate final answer
  ↓
Return text + product cards
```

Nếu câu hỏi mơ hồ hoặc kết quả MongoDB ít:

```text
User message
  ↓
Intent Router detect: recommendation
  ↓
Extract recommendation filters
  ↓
Query MongoDB bằng filter cứng
  ↓
Kết quả ít hoặc query có tính semantic
  ↓
Vector Search products
  ↓
Lấy product_id từ vector result
  ↓
Query MongoDB lại để lấy giá/tồn kho mới nhất
  ↓
Merge + rank products
  ↓
LLM generate final answer
```


### 7.10. Prompt generate recommendation answer

```text
Bạn là chatbot tư vấn cây cảnh cho app bán cây.

Nguyên tắc:
- Chỉ gợi ý sản phẩm có trong danh sách được cung cấp.
- Không tự bịa giá, tồn kho, size hoặc thông tin sản phẩm.
- Giải thích ngắn gọn vì sao sản phẩm phù hợp với nhu cầu user.
- Trả lời thân thiện, rõ ràng bằng tiếng Việt.
- Gợi ý tối đa 3 sản phẩm tốt nhất.

User cần tư vấn:
{{user_message}}

Điều kiện đã hiểu:
{{filters_json}}

Danh sách sản phẩm:
{{products_json}}

Hãy trả lời theo format:
1. Một câu mở đầu ngắn.
2. Danh sách sản phẩm đề xuất, mỗi sản phẩm gồm:
   - Tên
   - Giá
   - Lý do phù hợp
   - Lưu ý chăm sóc ngắn nếu có
3. Một câu hỏi follow-up nhẹ nếu cần.
```


## 8. Flow Vector Search cho Product Recommendation

### 8.1. Mục tiêu

Vector Search dùng để tìm sản phẩm theo **ý nghĩa** thay vì chỉ filter/keyword.

Ví dụ user hỏi:

```text
Tôi muốn cây chill chill để bàn làm việc.
Tôi muốn cây nhìn sang cho phòng khách.
Cây nào hợp người mới chơi?
Cây nào ít phải chăm mà vẫn đẹp?
Tôi cần cây làm quà tặng sinh nhật.
```

Những câu như `chill chill`, `nhìn sang`, `hợp người mới`, `làm quà` thường không thể query chính xác bằng MongoDB filter nếu data chưa có field tương ứng.

---

### 8.2. Nguyên tắc quan trọng

Vector DB không phải nguồn sự thật cho giá/tồn kho.

Flow đúng:

```text
Vector Search → lấy product_id
MongoDB → lấy thông tin mới nhất của product/variant/inventory
LLM → diễn giải kết quả
```

Không nên trả lời giá/tồn kho từ text đã embed, vì text đó có thể cũ.

---

### 8.3. Data cần embed

Nên tạo một đoạn text đại diện cho mỗi product.

Ví dụ product (logic thật có thể khác, này chỉ ví dụ):

```json
{
  "name": "Snake Plant",
  "short_description": "Cây lưỡi hổ dễ chăm, chịu thiếu sáng tốt.",
  "description": "Snake Plant là cây indoor phổ biến...",
  "care_level": "easy",
  "light_requirement": "low",
  "watering_need": "low",
  "indoor_outdoor": "indoor",
  "suitable_locations": ["bedroom", "office", "desk"],
  "suitable_for": ["beginner", "busy_people", "office_decor"],
  "tags": ["easy care", "low light", "modern", "minimal"]
}
``

Embedding text:

```text
Tên cây: Snake Plant.
Mô tả ngắn: Cây lưỡi hổ dễ chăm, chịu thiếu sáng tốt.
Mô tả: Snake Plant là cây indoor phổ biến, phù hợp người mới chơi cây, người bận rộn hoặc hay quên tưới.
Mức chăm sóc: easy.
Ánh sáng: low.
Nhu cầu tưới nước: low.
Phù hợp đặt ở: bedroom, office, desk.
Phù hợp cho: beginner, busy_people, office_decor.
Tags: easy care, low light, modern, minimal.
```


---

### 8.4. Function build embedding text

này chỉ là ví dụ, cần discuss lại để thêm trường nào hay db mới vào để thực hiện phần này.

```ts
function buildProductEmbeddingText(product: Product) {
  return [
    `Tên cây: ${product.name}.`,
    `Mô tả ngắn: ${product.short_description || ""}.`,
    `Mô tả: ${product.description || ""}.`,
    `Mức chăm sóc: ${product.care_level || "unknown"}.`,
    `Ánh sáng: ${product.light_requirement || "unknown"}.`,
    `Nhu cầu tưới nước: ${product.watering_need || "unknown"}.`,
    `Độ ẩm: ${product.humidity_need || "unknown"}.`,
    `Trong nhà/ngoài trời: ${product.indoor_outdoor || "unknown"}.`,
    `An toàn cho thú cưng: ${product.pet_safe === true ? "có" : product.pet_safe === false ? "không" : "không rõ"}.`,
    `Phù hợp đặt ở: ${(product.suitable_locations || []).join(", ")}.`,
    `Phù hợp cho: ${(product.suitable_for || []).join(", ")}.`,
    `Tags: ${(product.tags || []).join(", ")}.`,
    `Hướng dẫn chăm sóc: ${JSON.stringify(product.care_guide || {})}.`
  ].join("\n");
}
```


## 9. Flow Plant Care RAG

### 9.1. Mục tiêu

Plant Care RAG dùng để trả lời câu hỏi kiến thức chăm cây dựa trên tài liệu/knowledge base của app.

Ví dụ user hỏi:

```text
Tại sao cây Monstera bị vàng lá?
Cây lưỡi hổ tưới bao lâu một lần?
Cây bị úng rễ thì xử lý sao?
Có nên để cây trong phòng ngủ không?
Cây nào độc với mèo?
```

RAG phù hợp với kiến thức dạng text dài:

```text
- Bài viết chăm cây
- FAQ
- Blog
- Plant care guide
- Tài liệu nội bộ
- Hướng dẫn xử lý bệnh cây
```

---

### 9.2. Nguyên tắc quan trọng

LLM chỉ nên trả lời dựa trên context lấy từ knowledge base.

Nếu không đủ context, bot nên nói rõ:

```text
Mình chưa có đủ thông tin trong tài liệu hiện tại. Bạn có thể mô tả thêm tình trạng cây hoặc gửi ảnh nếu app có hỗ trợ.
```

Không nên để LLM tự bịa bệnh cây, thuốc xử lý, hóa chất hoặc hướng dẫn nguy hiểm.

---

### 9.3. Data source cho Plant Care RAG

Collection article gốc (này chỉ là mẫu, cần discuss để bàn lại):

```js
plant_knowledge_articles: [
  {
    _id: ObjectId,
    title: "Cách xử lý cây bị vàng lá",
    slug: "cach-xu-ly-cay-bi-vang-la",
    content: "Lá cây bị vàng thường do tưới quá nhiều nước, rễ bị úng hoặc cây thiếu ánh sáng...",
    related_plants: ["monstera-deliciosa", "pothos"],
    topics: ["yellow_leaves", "watering", "root_rot"],
    source_type: "article",
    is_active: true,
    created_at: Date,
    updated_at: Date
  }
]
```

Collection chunks:

```js
knowledge_chunks: [
  {
    _id: ObjectId,
    article_id: ObjectId,
    chunk_index: 0,
    title: "Cách xử lý cây bị vàng lá",
    content: "Lá cây bị vàng thường do tưới quá nhiều nước, rễ bị úng hoặc cây thiếu ánh sáng...",
    embedding_model: "bge-m3",
    embedding: [0.123, -0.456, 0.789],
    metadata: {
      topics: ["yellow_leaves", "watering", "root_rot"],
      related_plants: ["monstera-deliciosa", "pothos"],
      source_type: "article",
      slug: "cach-xu-ly-cay-bi-vang-la"
    },
    created_at: Date,
    updated_at: Date
  }
]
```


---

### 9.4. Ingest flow cho Knowledge Base

```text
Create/update article
  ↓
Clean markdown/html
  ↓
Split content thành chunks
  ↓
Generate embedding từng chunk
  ↓
Upsert vào knowledge_chunks
```

Chunk size gợi ý:

```text
- 500-1000 tokens/chunk
- overlap 50-150 tokens
```

Overlap giúp các đoạn không bị mất ngữ cảnh ở ranh giới chunk.


---

### 9.7. Runtime RAG flow

User hỏi:

```text
Tại sao cây Monstera bị vàng lá?
```

Flow:

```text
User message
  ↓
Intent Router detect: plant_care
  ↓
Extract plant_name/topic nếu có
  ↓
Embed user question
  ↓
Vector search knowledge_chunks
  ↓
Optional filter by related_plants/topic
  ↓
Take top 3-5 chunks
  ↓
Build context
  ↓
LLM answer based on context
  ↓
Return answer + sources
```