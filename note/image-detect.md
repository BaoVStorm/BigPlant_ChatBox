# Image-Aware Chat Flow

Tài liệu này mô tả riêng luồng khi user gửi **text kèm image**.

## 1. Mục tiêu

Khi user gửi một câu hỏi kèm ảnh cây, app phải hiểu rằng câu hỏi đang nói về **cây trong ảnh**.

Ví dụ:

```txt
cây này giá bao nhiêu
cây này còn hàng không
cây này có độc với mèo không
```

## 2. Ý tưởng xử lý

App không tự nhận diện hình ảnh trong chính server chatbot.

Thay vào đó, app gọi sang backend BigPlant khác để detect cây trong ảnh.

Luồng tổng quát:

```txt
User gửi text + image
→ chatbot server nhận request
→ chatbot gọi BigPlant_Backend detect ảnh
→ BigPlant_Backend trả label + plant + detect_result
→ chatbot dùng kết quả đó để suy ra cây đang được hỏi
→ chatbot tiếp tục flow Product Info / Plant Care / các flow liên quan
```

## 3. Contract của backend detect ảnh

Backend kia nhận:

```txt
POST /api/plant_detect
Content-Type: multipart/form-data
field file = image file
query topk
query two_pass
```

Backend kia trả:

```txt
success
label
scientific_name_search
plant
detect_result
```

Trong đó:

```txt
label
  → nhãn cây backend detect ra

scientific_name_search
  → tên chuẩn hóa dùng để tìm cây trong DB

plant
  → thông tin cây backend đã tìm thấy trong DB của nó

detect_result
  → raw result từ model detect phía sau
```

## 4. App chatbot nhận image như thế nào

App chatbot hiện mở rộng request để nhận thêm trường:

```txt
image
```

Image có thể được biểu diễn dưới dạng JSON-friendly để mobile app dễ gửi:

```txt
data_url
base64
url
filename
content_type
mock_label
```

## 5. Mock image flow để test local

Để dễ test và dễ phát triển, flow detect ảnh có hỗ trợ mock.

Nếu request gửi:

```txt
image.mock_label
```

thì chatbot sẽ không gọi server detect thật, mà dựng ra một detect result giả tương ứng với label đó.

Điều này rất hữu ích khi:

```txt
backend detect thật chưa bật
muốn test flow product_info bằng ảnh mà không cần gửi file ảnh thật
muốn debug logic chat nhanh hơn
```

## 6. Flow chi tiết khi có image

Khi request có image, app làm thêm một bước trước khi dispatch intent:

```txt
1. resolve image context
2. gọi plant detect client hoặc mock detect
3. nhận detection result
4. nếu detect thành công thì cố resolve sang product trong DB chatbot
5. nếu resolve được product thì tạo resolved product context
6. đưa image context đó vào metadata và vào flow xử lý tiếp theo
```

## 7. App dùng detect result như thế nào

Kết quả detect không phải câu trả lời cuối cùng. Nó chỉ là **ngữ cảnh bổ sung** để app biết user đang nói về cây nào.

Ví dụ:

```txt
image detect ra abrus_precatorius
→ chatbot resolve được product Jequirity bean
→ nếu user hỏi "cây này còn hàng không"
   thì app dùng product context đó để trả lời tồn kho
```

## 8. Khi nào image context làm đổi flow

### Trường hợp 1: intent đã rõ sẵn

Ví dụ:

```txt
cây này giá bao nhiêu
```

Router đã nhận ra đây là `product_info`.
Image context lúc này chỉ bổ sung `product_name` và product context để handler biết cây nào đang được hỏi.

### Trường hợp 2: intent mơ hồ nhưng có ảnh

Ví dụ:

```txt
cây này sao
```

Nếu không có ảnh, câu này rất mơ hồ.
Nhưng nếu có ảnh và detect resolve được product, app sẽ fallback theo hướng:

```txt
coi đây là product_info theo ảnh
```

Mục tiêu:

```txt
giúp user không cần gõ tên cây
vẫn hỏi được theo kiểu "cây này ..." khi đã gửi ảnh
```

## 9. Flow ảnh với Product Info

Đây là flow quan trọng nhất của image-aware chat.

Ví dụ:

```txt
cây này giá bao nhiêu
cây này còn hàng không
cây này có độc với mèo không
```

Luồng:

```txt
image detect ra cây gì
→ resolve sang product trong DB chatbot
→ build full product context
→ Product Info trả lời như bình thường, nhưng dùng cây từ ảnh làm subject
```

## 10. Flow ảnh với độc tính

Ví dụ:

```txt
cây này có độc với mèo không
```

Luồng:

```txt
image detect ra cây gì
→ resolve product
→ lấy plants.toxicity_warning / safety_notes
→ trả lời tập trung vào độc tính/an toàn
```

Điểm quan trọng:

```txt
không mở đầu bằng giá hoặc tồn kho
nếu user hỏi độc tố thì trả lời theo hướng độc tính trước
```

## 11. Nếu detect thất bại thì sao

Nếu detect không ra cây hoặc không resolve được product, app không nên bịa.

Nó có thể:

```txt
1. nói chưa nhận diện được cây trong ảnh
2. hoặc yêu cầu user gửi ảnh rõ hơn / nêu tên cây nếu biết
```

## 12. Tách lớp cho dễ đọc và dễ sửa

Flow detect ảnh đã được tách riêng theo đúng tinh thần clean structure:

```txt
schema input/output riêng
mock detect riêng
client gọi BigPlant_Backend riêng
service resolve image context riêng
chat service chỉ điều phối
```

Ý nghĩa:

```txt
đổi backend detect sau này dễ hơn
mock test dễ hơn
source code dễ đọc hơn
```
