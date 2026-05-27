# BigPlant Chatbot Version V2

File này ghi lại những thay đổi kiến trúc và logic đã thêm vào sau bản flow cơ bản.

## 1. Mục tiêu của V2

V2 tập trung giải quyết 2 vấn đề lớn:

```txt
1. bot nhớ được ngữ cảnh qua nhiều lượt chat
2. bot trả lời xong vẫn tiếp tục dẫn dắt user hỏi thêm
```

Đồng thời V2 cũng mở rộng flow ảnh để text + image hoạt động giống hội thoại thật hơn.

## 2. Những thay đổi lớn trong V2

### A. Session memory trong MongoDB

Đã thêm 2 collection:

```txt
chat_sessions
chat_messages
```

`chat_sessions` lưu memory của phiên chat:

```txt
active_subject
last_intent
last_user_message
last_assistant_message
last_image_detection
preferences
```

`chat_messages` lưu lịch sử từng turn:

```txt
session_id
user_id
role
content
extra metadata
created_at
```

### B. Active subject memory

Hệ thống đã nhớ cây/sản phẩm đang được nói tới.

Ví dụ:

```txt
user gửi ảnh
→ detect ra cây
→ resolve sang product
→ lưu active_subject
→ user hỏi tiếp "cây này còn hàng không"
→ bot hiểu "cây này" là cây nào
```

### C. Follow-up message và suggested questions

Response không còn chỉ có `message`.

Hiện đã có thêm:

```txt
follow_up_message
suggested_questions
session_id
```

Ý nghĩa:

```txt
bot trả lời xong vẫn chủ động gợi ý user hỏi tiếp
phù hợp cho mobile app render quick chips / suggested prompts
```

### D. Image-aware chat

Đã thêm flow nhận `image` trong request chat.

Image có thể gửi dưới dạng:

```txt
data_url
base64
url
mock_label
```

Bot sẽ gọi sang backend detect ảnh hoặc dùng mock, rồi resolve sang product context.

### E. Facet classification

Đã thêm lớp `facet` để hiểu sâu hơn câu hỏi bên trong intent.

Ví dụ trong `product_info`:

```txt
price
stock
toxicity
variant
image
highlights
overview
```

Ví dụ trong `recommendation`:

```txt
budget_filtered
beginner_friendly
placement_based
light_based
watering_based
gift_based
style_based
generic
```

Ý nghĩa:

```txt
intent chỉ nói user đang hỏi loại gì
facet nói user đang hỏi chính xác khía cạnh nào trong loại đó
```

### F. Preference memory

Bot bắt đầu nhớ preference từ hội thoại:

```txt
max_price
budget_input_currency
care_level
watering_need
light_requirement
placement
pet_safe
```

Các preference này được lưu trong `chat_sessions.memory.preferences`.

### G. Dialogue policy

Đã thêm lớp chính sách hội thoại để xử lý các trường hợp bot không nên chỉ dựa vào intent thô.

Ví dụ:

```txt
user gửi ảnh nhưng không nhắn gì
→ fallback sang product_info overview

user đang hỏi tiếp về cây vừa nói tới
→ kéo context_subject từ session vào

user hỏi tiếp sau recommendation kiểu "có loại nào rẻ hơn không"
→ coi đó là recommendation refinement thay vì product_info
```

### H. Recommendation refinement

Đã thêm refinement logic dùng memory từ session trước.

Ví dụ:

```txt
Lượt 1: tôi muốn cây dễ chăm dưới 400K
→ bot lưu budget + care_level + last_recommendations

Lượt 2: có loại nào rẻ hơn không?
→ bot dùng top recommendation trước đó làm reference price
→ chỉ trả các cây rẻ hơn reference đó
```

## 3. Hành vi mới của V2

### 3.1. Gửi ảnh nhưng không nhắn gì

Trước đây:

```txt
bot có thể không biết nên làm gì hoặc route sai
```

Hiện tại:

```txt
nếu có ảnh và detect resolve được product
→ app sẽ fallback sang product_info overview
```

### 3.2. Hỏi tiếp sau khi gửi ảnh

Trước đây:

```txt
bot quên cây vừa nói tới
```

Hiện tại:

```txt
bot nhớ active_subject theo session
→ câu tiếp theo kiểu "cây này còn hàng không" hoạt động đúng
```

### 3.3. Câu hỏi độc tố

Trước đây:

```txt
có thể trả lời giống product info chung chung, lẫn giá/tồn kho
```

Hiện tại:

```txt
nếu facet là toxicity
→ bot trả lời theo hướng an toàn/độc tính trước
→ không mở đầu bằng giá và tồn kho
```

### 3.4. Follow-up thông minh hơn

Trước đây:

```txt
chỉ có message chính
```

Hiện tại:

```txt
message chính
follow_up_message
suggested_questions
```

### 3.5. Câu hỏi tiếp theo theo ngữ cảnh đã tốt hơn

Trước đây:

```txt
user hỏi tiếp "cây này còn hàng không" hoặc "có loại nào rẻ hơn không"
→ bot dễ quên hoặc route sai
```

Hiện tại:

```txt
bot có thể dùng active_subject và preferences trong session
→ hiểu câu hỏi tiếp theo theo đúng ngữ cảnh trước đó
```

## 4. Những gì V2 đã tốt hơn

```txt
bot nhớ được ngữ cảnh hội thoại
bot hiểu follow-up như "cây này" tốt hơn
bot hỗ trợ image-aware conversation
bot không dừng đột ngột sau mỗi câu trả lời
bot bắt đầu có preference memory
bot trả lời độc tính đúng trọng tâm hơn
bot hiểu refinement theo session tốt hơn
bot có facet classification để hiểu sâu hơn câu hỏi trong từng intent
```

## 5. Những gì V2 vẫn chưa hoàn hảo

```txt
preference memory mới ở mức cơ bản
active_subject hiện chủ yếu là 1 product chính, chưa hỗ trợ nhiều subject song song
plant care vẫn phụ thuộc mạnh vào knowledge base hiện có
general chat vẫn có thể chậm nếu dùng local LLM CPU-only
clarification policy vẫn chưa đủ sâu để hỏi lại khi thiếu slot quan trọng
```

## 6. Hướng nâng cấp tiếp theo sau V2

### Gợi ý 1: Clarification policy

Ví dụ:

```txt
user hỏi recommendation quá chung
→ thay vì trả top 3 ngay, bot hỏi lại budget / ánh sáng / vị trí
```

### Gợi ý 2: Preference-aware recommendation

Ví dụ:

```txt
user từng nói có mèo
→ recommendation lần sau tự ưu tiên cây an toàn hơn
```

### Gợi ý 3: Context summary

Sau nhiều lượt chat, có thể tóm tắt session thành memory gọn hơn thay vì chỉ lưu turn-by-turn.

### Gợi ý 4: Multi-subject memory

Ví dụ:

```txt
user vừa hỏi 3 cây khác nhau
→ bot nên nhớ top products gần nhất thay vì chỉ 1 active_subject
```
