## Hybrid chatbot nên vận hành theo hướng:

```txt
MongoDB/API = nguồn dữ liệu thật
LLM = hiểu câu hỏi + diễn giải kết quả
Vector Search = tìm theo ý nghĩa khi filter cứng không đủ
Plant Facts / RAG = trả lời kiến thức chăm cây
Router = quyết định câu hỏi đi theo nhánh nào
```

## Kiến trúc tổng thể

```txt
User
 ↓
Chat UI
 ↓
Chat Backend API
 ↓
Intent Router
 ├── Product Info       → MongoDB products + variants + inventory + images + plants
 ├── Recommendation     → MongoDB filter + Vector Search
 ├── Plant Care Q&A     → plants facts / Knowledge Base / RAG
 ├── Cart Order         → Cart API / Order API
 └── General Chat       → LLM
 ↓
LLM Response Generator
 ↓
User
```

# I. Chia chatbot thành các nhóm chức năng

Không nên làm một chatbot “hỏi gì cũng ném vào LLM”. Nên chia thành intent rõ ràng.

## 1. Product Info

Dùng cho câu hỏi về một sản phẩm cây cụ thể.

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây Monstera còn hàng không?
Cây này có mấy loại?
Cây trầu bà có độc với mèo không?
```

Nguồn dữ liệu thật:

```txt
products
product_variants
variant_inventory
product_images
plants
product_categories
```

Nguyên tắc:

```txt
Không để LLM tự đoán giá.
Không để LLM tự đoán tồn kho.
Không để LLM tự đoán độc tính.
Không để LLM tự đoán size/variant.
```

## 2. Recommendation

Dùng cho tư vấn chọn cây theo nhu cầu.

Ví dụ:

```txt
Tôi muốn cây dễ chăm để bàn làm việc.
Tôi hay quên tưới thì nên mua cây nào?
Phòng tôi ít nắng, nên chọn cây gì?
Tôi muốn cây nhìn sang cho phòng khách.
```

Nguồn dữ liệu:

```txt
MongoDB filter trên dữ liệu có thật
+
Vector search trên embedding text của product/plant
```

Phân loại nhu cầu:

```txt
giá dưới 300k             → filter qua product_variants.price
dễ chăm                   → filter qua products.care_level nếu dữ liệu có chuẩn hóa
còn hàng                  → filter qua variant_inventory.available_qty
ít nắng                   → semantic/vector search nếu chưa có field cứng
để bàn                    → semantic/vector search
nhìn sang                 → semantic/vector search
hợp người mới             → semantic/vector search
```

## 3. Plant Care Q&A

Dùng cho kiến thức chăm cây, an toàn cây và thông tin cây nền.

Ví dụ:

```txt
Tại sao lá Monstera bị vàng?
Cây lưỡi hổ tưới bao lâu một lần?
Cây này có độc với thú cưng không?
Có nên để cây trong phòng ngủ không?
```

Nguồn dữ liệu:

```txt
plants.description
plants.toxicity_warning
plants.safety_notes
plants.uses
plants.advantages
knowledge base / articles / FAQ nếu có collection riêng
```

Hướng xử lý:

```txt
Nếu câu hỏi là factual về cây cụ thể → trả lời từ plants
Nếu câu hỏi là kiến thức chăm cây tổng quát → search knowledge base / RAG nếu có
Nếu không đủ context → nói rõ chưa có đủ thông tin trong tài liệu hiện tại
```

# II. Dữ liệu MongoDB chatbot cần dùng

## 1. `product_categories`

Hiện category chính có 2 nhóm:

```txt
Plants
Pots
```

Giai đoạn hiện tại chatbot chỉ cần tập trung nhóm `Plants`.

Các field quan trọng:

```txt
_id
name
slug
description
is_active
sort_order
parent_id
```

Ý nghĩa:

```txt
Sản phẩm recommendation mặc định nên ưu tiên category Plants.
Không cần đưa Pots vào flow recommendation cây ở giai đoạn đầu.
```

## 2. `plants`

Đây là dữ liệu cây nền/thực vật học.

Các field quan trọng:

```txt
_id
scientific_name
scientific_name_search
common_name
family
taxonomic_order
genus
species
taxonomic_status
uses
advantages
description
toxicity_warning
safety_notes
evidence_level
source
```

Ý nghĩa:

```txt
Độc tính/an toàn thú cưng lấy từ plants.toxicity_warning và plants.safety_notes.
Mô tả cây nền lấy từ plants.description.
Công dụng/ưu điểm lấy từ plants.uses và plants.advantages.
```

## 3. `products`

Đây là sản phẩm cha trong shop.

Các field quan trọng:

```txt
_id
category_id
plant_id
sku
product_type
name
slug
short_description
description
care_level
rating_avg
rating_count
is_active
created_at
updated_at
```

Ý nghĩa:

```txt
name/slug/sku là các field chính để tìm sản phẩm.
care_level là filter cứng quan trọng cho recommendation nếu dữ liệu đã chuẩn hóa.
product_type hiện là plant cho dữ liệu cây.
```

## 4. `product_variants`

Đây là nơi có biến thể bán hàng và giá thật.

Các field quan trọng:

```txt
_id
product_id
variant_sku
variant_name
attributes
price
compare_at_price
weight_gram
is_default
is_active
```

Ý nghĩa:

```txt
Giá thật phải lấy từ product_variants.price.
Variant/size/option phải đọc từ variant_name và attributes.
```

## 5. `variant_inventory`

Đây là nơi có tồn kho thật theo variant.

Các field quan trọng:

```txt
_id
variant_id
available_qty
reserved_qty
sold_qty
updated_at
```

Ý nghĩa:

```txt
“Còn hàng không?” phải dựa trên available_qty.
Không được suy ra tồn kho từ products hay product_variants.
```

## 6. `product_images`

Đây là nơi có ảnh theo product hoặc variant.

Các field quan trọng:

```txt
_id
product_id
variant_id
image_url
alt_text
sort_order
is_primary
created_at
```

Ý nghĩa:

```txt
Product card nên ưu tiên ảnh is_primary=true.
Nếu user hỏi ảnh variant cụ thể thì query theo variant_id trước.
```

## 7. Quan hệ dữ liệu quan trọng

```txt
products.category_id         → product_categories._id
products.plant_id            → plants._id
product_variants.product_id  → products._id
variant_inventory.variant_id → product_variants._id
product_images.product_id    → products._id
product_images.variant_id    → product_variants._id
```

# III. Tool/function cho chatbot

LLM không nên tự query MongoDB trực tiếp. Nên expose các function an toàn.

## Product tools

```js
getProductByNameOrSlugOrSku(query)
getProductFullContext(productId)
getProductVariants(productId)
getVariantInventory(variantIds)
getProductImages(productId, variantIds)
```

`getProductFullContext(productId)` nên trả về:

```txt
product
category
plant
variants
inventories
images
computed.price_min
computed.price_max
computed.available_qty
computed.primary_image_url
```

## Recommendation tools

```js
searchPlantProducts(filters)
semanticSearchPlantProducts(query, hardFilters)
rankPlantProducts(candidates, filters)
```

## Knowledge tools

```js
getPlantFactsByName(name)
getPlantFactsByProduct(productId)
searchPlantKnowledge(query)
```

# IV. Intent Router

Router có nhiệm vụ phân loại message vào một intent:

```txt
product_info
recommendation
plant_care
cart_order
general
unclear
```

Ví dụ:

```txt
"Cây Monstera bao nhiêu tiền?"         → product_info
"Tôi muốn cây dễ chăm để bàn làm việc" → recommendation
"Tại sao lá cây bị vàng?"              → plant_care
"Thêm cây này vào giỏ hàng"            → cart_order
"Xin chào"                             → general
```

Entity router nên hiểu:

```txt
product_name  → tìm trong products và có thể fallback sang plants
max_price     → lọc qua product_variants.price
care_level    → lọc qua products.care_level
in_stock      → lọc qua variant_inventory.available_qty
placement     → semantic/vector search
light_need    → semantic/vector search
watering_need → semantic/vector search
```

# V. Flow xử lý message chuẩn

```js
async function handleChatMessage(userId, message) {
  const route = await classifyIntent(message)

  switch (route.intent) {
    case "product_info":
      return handleProductInfo(message, route)

    case "recommendation":
      return handleRecommendation(message, route)

    case "plant_care":
      return handlePlantCare(message, route)

    case "cart_order":
      return handleCartOrder(message, route)

    case "general":
      return handleGeneralChat(message)

    default:
      return {
        message: "Bạn muốn hỏi về cây nào, muốn mình tư vấn chọn cây, hay hỏi cách chăm cây?"
      }
  }
}
```

# VI. Flow Product Info

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây Monstera còn hàng không?
Cây này có độc với mèo không?
```

Flow chuẩn:

```txt
1. Router detect product_info
2. Extract product_name hoặc lấy product context từ session nếu user nói "cây này"
3. Query products bằng name/slug/sku
4. Chỉ lấy product is_active=true và ưu tiên category Plants / product_type='plant'
5. Query product_categories bằng products.category_id
6. Query plants bằng products.plant_id
7. Query product_variants bằng products._id
8. Query variant_inventory bằng variant._id
9. Query product_images bằng product._id hoặc variant._id
10. Tạo factual product context
11. Đưa context cho LLM diễn giải
12. Return text + product card
```

Context cho LLM nên gồm:

```txt
product
category
plant
variants
inventory per variant
images
computed.price_text
computed.available_qty
computed.in_stock
```

Nguyên tắc trả lời:

```txt
Hỏi giá:
  - tính từ variants.price

Hỏi còn hàng:
  - dựa vào variant_inventory.available_qty

Hỏi có mấy loại/mấy size:
  - đọc variant_name và attributes

Hỏi độc tính/an toàn thú cưng:
  - dựa vào plants.toxicity_warning và plants.safety_notes

Hỏi ảnh:
  - lấy product_images, ưu tiên is_primary=true
```

Fallback:

```txt
Không tìm thấy sản phẩm:
  Mình chưa tìm thấy cây/sản phẩm này trong hệ thống.

Có sản phẩm nhưng chưa có variants:
  Mình tìm thấy sản phẩm nhưng hiện chưa có dữ liệu giá/biến thể.

Có variants nhưng chưa có inventory:
  Mình có dữ liệu giá nhưng chưa có dữ liệu tồn kho hiện tại.

Không có dữ liệu plants:
  Mình có dữ liệu sản phẩm nhưng chưa có thông tin cây nền/an toàn chi tiết.
```

# VII. Flow Recommendation

Ví dụ:

```txt
Tôi muốn cây dễ chăm dưới 300k.
Tôi hay quên tưới thì nên mua cây nào?
Phòng tôi ít nắng, nên chọn cây gì?
Tôi muốn cây nhìn sang cho phòng khách.
```

Nguyên tắc:

```txt
Chỉ filter cứng trên field có thật trong MongoDB.
Những nhu cầu không có field cứng thì đi vector search.
LLM chỉ dùng để diễn giải kết quả cuối cùng.
```

Filter cứng hiện có thể dùng:

```txt
product thuộc category Plants hoặc product_type='plant'
products.is_active=true
products.care_level nếu user hỏi dễ chăm
product_variants.price <= max_price
variant_inventory.available_qty > 0 nếu user có ý mua ngay
```

Nhu cầu nên dùng vector search:

```txt
ít nắng
thiếu sáng
để bàn
phòng ngủ
phòng khách
văn phòng
nhìn sang
minimal
hay quên tưới
hợp người mới
làm quà
```

Flow recommendation:

```txt
1. Router detect recommendation
2. Extract hard filters: max_price, care_level, in_stock
3. Luôn restrict về category Plants / product_type='plant'
4. Query products + variants + inventory để lấy candidate
5. Nếu query có semantic intent hoặc candidate quá ít
6. Vector search trên embedding text
7. Lấy product _id từ vector search
8. Query MongoDB lại để lấy dữ liệu thật mới nhất
9. Merge + rank
10. LLM diễn giải tối đa 3 sản phẩm
11. Return text + product cards
```

Ranking nên ưu tiên:

```txt
1. In stock
2. Match care_level
3. Match budget
4. Vector score
5. Rating nếu cần tie-break
```

Product card nên có:

```txt
product._id
name
slug
short_description
category_name
plant_common_name / plant_scientific_name
price_text
available_qty
in_stock
primary_image_url
reason
```

# VIII. Product Vector Search

Mục tiêu: tìm sản phẩm theo ý nghĩa khi filter cứng không đủ.

Ví dụ:

```txt
Tôi muốn cây chill chill để bàn làm việc.
Tôi muốn cây nhìn sang cho phòng khách.
Cây nào hợp người mới chơi?
Cây nào ít phải chăm mà vẫn đẹp?
```

Nguyên tắc quan trọng:

```txt
Vector search không phải nguồn sự thật cho giá/tồn kho.
Vector search chỉ để lấy danh sách product phù hợp theo nghĩa.
Sau đó phải query lại MongoDB để lấy dữ liệu thật.
```

Embedding text nên build từ field hiện có:

```txt
products.name
products.sku
products.product_type
product_categories.name
products.short_description
products.description
products.care_level
plants.scientific_name
plants.common_name
plants.description
plants.uses
plants.advantages
plants.toxicity_warning
plants.safety_notes
plants.evidence_level
product_variants.variant_name
product_variants.attributes
```

Không nên embed dữ liệu thay đổi nhanh:

```txt
variant_inventory.available_qty
price động nếu thay đổi thường xuyên
```

# IX. Flow Plant Care

Plant Care hiện nên chia thành 2 lớp.

## 1. Plant facts

Áp dụng cho câu hỏi factual về cây cụ thể:

```txt
Cây này có độc không?
Có an toàn với mèo không?
Công dụng của cây này là gì?
```

Nguồn trả lời:

```txt
plants.toxicity_warning
plants.safety_notes
plants.description
plants.uses
plants.advantages
plants.evidence_level
```

## 2. Plant care knowledge / RAG

Áp dụng cho câu hỏi kiến thức rộng hơn:

```txt
Tại sao lá cây bị vàng?
Cây bị úng rễ thì xử lý sao?
Có nên tưới cây mỗi ngày không?
```

Flow:

```txt
Nếu có knowledge base / knowledge_chunks:
  search tài liệu liên quan
  → lấy top chunks
  → đưa context cho LLM

Nếu chưa có knowledge base phù hợp:
  trả lời là chưa có đủ thông tin trong tài liệu hiện tại
  → không tự bịa nguyên nhân, thuốc hoặc cách xử lý nguy hiểm
```

# X. Local model

Vai trò của local LLM trong hệ thống:

```txt
1. Router fallback khi câu quá mơ hồ
2. Diễn giải factual product context thành câu trả lời tự nhiên
3. Diễn giải recommendation thành câu tư vấn dễ hiểu
4. Trả lời general chat
5. Trả lời Plant Care khi đã có context facts hoặc RAG
```

Khuyến nghị hiện tại:

```txt
Mặc định: Qwen2.5-7B-Instruct Q4_K_M
So sánh: Meta-Llama-3.1-8B-Instruct Q4_K_M
Thiên tiếng Việt: VinaLLaMA-7B-Chat Q5_0
Embedding: BAAI/bge-m3
```

Nguyên tắc cuối cùng:

```txt
MongoDB/API quyết định dữ liệu thật.
LLM không được bịa giá, tồn kho, size, ảnh hoặc độc tính.
Vector search chỉ giúp tìm theo ý nghĩa.
Recommendation phải query lại MongoDB trước khi trả lời.
Plant Care phải có context facts hoặc RAG trước khi LLM trả lời.
```
