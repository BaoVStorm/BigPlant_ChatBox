# Product Info Flow

Intent này dùng khi user hỏi về một sản phẩm cây cụ thể.

## Khi nào vào flow này

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây này còn hàng không?
Cây Jequirity bean có độc với mèo không?
Cho mình xem thông tin cây này.
```

## Router nhận diện như thế nào

Flow này thường được bắt bởi các tín hiệu như:

```txt
giá
bao nhiêu tiền
còn hàng
tồn kho
size
hình ảnh
độc tính
an toàn với thú cưng
```

Ngoài ra semantic layer còn bắt các câu gần nghĩa như:

```txt
shop còn mẫu này không
cho mình xem thông tin cây aloe vera
```

## Dữ liệu mà flow này dùng

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
```

## App làm gì sau khi detect được product_info

```txt
1. tìm tên cây/sản phẩm nếu có trong câu hỏi
2. tìm product tương ứng trong MongoDB
3. nếu có product thì gom full product context
4. full product context gồm:
   - product cha
   - category
   - variants
   - inventory theo variant
   - images
   - plant facts nếu có
5. từ context đó, app tự tính:
   - giá thấp nhất / cao nhất
   - tổng tồn kho
   - trạng thái còn hàng
   - ảnh chính
6. build câu trả lời deterministic
7. trả về text + product card
```

## Điểm quan trọng

Flow này hiện không dùng LLM để trả lời.

Lý do:

```txt
cần độ đúng factual cao
MongoDB đã có dữ liệu thật
tránh hallucination
tránh chậm
```

## Nhánh độc tính trong Product Info

Nếu user hỏi về độc tố/thú cưng, app sẽ ưu tiên trả lời theo hướng an toàn/độc tính trước.

Ví dụ:

```txt
Cây này có độc với mèo không?
```

Khi đó app sẽ ưu tiên đọc:

```txt
plants.toxicity_warning
plants.safety_notes
```

và trả lời theo hướng:

```txt
có độc / chưa đủ dữ liệu / tương đối an toàn
```

thay vì mở đầu bằng giá hoặc tồn kho.
