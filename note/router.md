# Router Flow

Router là lớp đầu tiên quyết định người dùng đang hỏi loại gì.

## Mục tiêu của router

Router không trả lời trực tiếp. Router chỉ làm 2 việc:

```txt
1. nhận diện intent
2. rút ra entity để các flow phía sau dùng tiếp
```

## Router 3 tầng

Hệ thống hiện tại dùng 3 tầng:

```txt
Tầng 1: weighted rules
Tầng 2: semantic examples
Tầng 3: local LLM fallback
```

## Tầng 1: weighted rules

Tầng này dùng các tín hiệu rõ ràng.

Ví dụ:

```txt
bao nhiêu tiền
còn hàng không
thêm vào giỏ
vàng lá
xin chào
```

Mỗi tín hiệu có trọng số riêng. Sau khi cộng điểm, hệ thống so intent cao nhất với intent thứ hai. Nếu chênh lệch đủ lớn thì chốt ngay, không cần gọi embedding hay LLM.

Điểm mạnh:

```txt
nhanh
dễ kiểm soát
tốt cho câu hỏi quen thuộc
```

Điểm yếu:

```txt
khó bắt paraphrase nếu user nói quá khác marker
```

## Tầng 2: semantic examples

Nếu rules chưa đủ chắc, hệ thống so câu hỏi với bộ câu mẫu của từng intent bằng embedding.

Ví dụ các câu kiểu:

```txt
shop còn mẫu này không
mình cần cây cho góc làm việc
lá cây bị úng thì cứu sao
alo bạn ơi
```

Tầng semantic giúp app hiểu được các câu gần nghĩa, ngay cả khi không dùng đúng marker.

Điểm mạnh:

```txt
bắt được paraphrase
hợp tiếng Việt tự nhiên hơn
giảm số lần phải gọi local LLM
```

Điểm yếu:

```txt
chậm hơn rules vì phải embed query
```

## Tầng 3: local LLM fallback

Nếu rules và semantic đều chưa đủ chắc, app mới cho local LLM phân loại intent.

Mục tiêu của tầng này:

```txt
xử lý các câu thật sự mơ hồ
giữ tính linh hoạt cho router
```

Điểm yếu:

```txt
chậm nhất trong 3 tầng
```

## Entity extraction

Ngoài intent, router còn rút ra entity như:

```txt
product_name
max_price
budget_input_currency
care_level
watering_need
light_requirement
placement
pet_safe
```

Các entity này không phải để trả lời ngay, mà để truyền sang flow xử lý sau đó.
