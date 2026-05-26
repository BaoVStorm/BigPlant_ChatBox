# Plant Care Flow

Intent này dùng cho câu hỏi chăm cây, bệnh cây, triệu chứng cây.

## Khi nào vào flow này

Ví dụ:

```txt
Tại sao lá cây bị vàng?
Lá cây bị úng thì cứu sao?
Cây tưới bao lâu một lần?
```

## Router nhận diện như thế nào

Flow này thường được bắt bởi các tín hiệu như:

```txt
vàng lá
úng rễ
thối rễ
héo lá
đốm lá
sâu bệnh
tưới bao lâu
chăm sóc
```

Semantic layer hỗ trợ thêm cho các câu gần nghĩa như:

```txt
lá cây bị úng thì cứu sao
cách cứu cây sắp chết
```

## Dữ liệu mà flow này dùng

```txt
knowledge_chunks
knowledge vector index
```

## App làm gì sau khi detect được plant_care

```txt
1. embed câu hỏi của user
2. search vector trên knowledge base
3. lấy các chunk gần nhất
4. build context từ các chunk đó
5. nếu local LLM available:
   - dùng LLM diễn giải context thành câu trả lời
6. nếu LLM fail:
   - fallback bằng cách lấy nội dung context gần nhất
7. nếu không có chunk phù hợp:
   - nói rõ là hiện chưa có đủ tài liệu
```

## Điểm quan trọng

Flow này chỉ dùng LLM sau khi đã có context phù hợp.

Ý nghĩa:

```txt
LLM không tự bịa plant care từ đầu
LLM chỉ diễn giải dựa trên tài liệu tìm thấy
```
