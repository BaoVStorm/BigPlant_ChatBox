# Recommendation Flow

Intent này dùng khi user muốn được tư vấn chọn cây theo nhu cầu.

## Khi nào vào flow này

Ví dụ:

```txt
Tôi muốn cây dễ chăm dưới 400K.
Mình cần cây cho góc làm việc.
Tôi muốn cây hợp người mới chơi.
Phòng ít nắng nên chọn cây gì?
```

## Router nhận diện như thế nào

Flow này thường được bắt bởi các tín hiệu như:

```txt
tư vấn
gợi ý
nên mua
nên chọn
phù hợp
để bàn
phòng khách
phòng ngủ
văn phòng
```

Semantic layer bắt thêm các câu như:

```txt
mình cần cây cho góc làm việc
mình muốn tìm một cây tặng sinh nhật
```

## Dữ liệu mà flow này dùng

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
vector index trên product embeddings
```

## App làm gì sau khi detect được recommendation

```txt
1. đọc các filters từ router
2. hard filter theo dữ liệu có thật:
   - care_level
   - max_price
   - in_stock
3. luôn ưu tiên nhóm Plants / product_type='plant'
4. lấy candidate products từ MongoDB
5. nếu query mang tính semantic hoặc candidate quá ít:
   - embed query
   - vector search trên product embeddings
   - lấy thêm candidate từ semantic search
6. hydrate lại toàn bộ candidate thành full product context
7. rank candidate
8. lấy top 3
9. build câu trả lời deterministic
10. trả product cards
```

## Hard filter hiện có

```txt
care_level  → products.care_level
max_price   → giá variant sau khi normalize currency
in_stock    → variant_inventory.available_qty
```

## Semantic recommendation hiện dùng cho loại nhu cầu nào

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

## Điểm quan trọng

Flow này hiện không dùng LLM để trả lời.

Lý do:

```txt
giữ tốc độ
giảm hallucination
vì phần recommendation hiện có thể build deterministic từ candidate thật
```
