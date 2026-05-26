# BigPlant AI System Flow

Tài liệu này mô tả **cách hệ thống AI của app đang thực sự vận hành**. Mục tiêu là giải thích rõ:

- Khi người dùng hỏi một câu thì hệ thống làm gì trước, làm gì sau.
- Hệ thống chia câu hỏi thành bao nhiêu nhóm.
- Mỗi nhóm được nhận diện như thế nào.
- Sau khi nhận diện được nhóm, hệ thống lấy dữ liệu và tạo câu trả lời ra sao.
- Model nào được dùng ở từng giai đoạn.

Tài liệu này chỉ tập trung vào **logic xử lý của app**, không đi sâu vào code hay tên hàm.

---

## 1. Tư tưởng thiết kế của hệ thống

Hệ thống không xem mọi câu hỏi đều là một bài toán của LLM.

Thay vào đó, app đi theo hướng:

```txt
1. Xác định người dùng đang hỏi loại gì.
2. Chuyển câu hỏi sang đúng nhánh xử lý.
3. Lấy dữ liệu thật từ MongoDB nếu câu hỏi cần dữ liệu sản phẩm.
4. Chỉ dùng LLM ở những chỗ cần hiểu ngữ nghĩa hoặc cần diễn giải.
```

Ý nghĩa của cách làm này:

```txt
- giảm việc model tự bịa
- tăng độ đúng cho giá/tồn kho/độc tính
- giúp app nhanh hơn ở các câu factual
- giúp giải thích flow hệ thống rõ ràng hơn
```

---

## 2. Một câu hỏi đi vào hệ thống như thế nào

Khi người dùng gửi một câu hỏi, app xử lý theo chuỗi sau:

```txt
Người dùng gửi câu hỏi
→ API nhận request
→ Bộ điều phối chat nhận message
→ Bộ router phân loại intent
→ Hệ thống chọn nhánh xử lý tương ứng
→ Nhánh đó query MongoDB hoặc gọi vector search / LLM tùy trường hợp
→ Tạo response cuối cùng
→ Trả về cho người dùng
```

Nói ngắn gọn, app có 3 lớp tư duy chính:

```txt
Lớp 1: Nhận diện người dùng đang muốn gì
Lớp 2: Lấy dữ liệu thật tương ứng với ý định đó
Lớp 3: Trả lời bằng format phù hợp
```

---

## 3. Các nhóm câu hỏi mà hệ thống đang hỗ trợ

Hiện tại app chia câu hỏi thành 6 nhóm:

```txt
1. product_info
2. recommendation
3. plant_care
4. cart_order
5. general
6. unclear
```

Ý nghĩa từng nhóm:

### product_info

Người dùng đang hỏi về **một sản phẩm cây cụ thể**.

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
Cây này còn hàng không?
Cây Jequirity bean có độc với mèo không?
Cho mình xem thông tin cây này.
```

### recommendation

Người dùng không hỏi một sản phẩm cụ thể, mà muốn **được tư vấn chọn cây theo nhu cầu**.

Ví dụ:

```txt
Tôi muốn cây dễ chăm dưới 400K.
Mình cần cây cho góc làm việc.
Tôi muốn cây hợp người mới chơi.
Phòng ít nắng nên chọn cây gì?
```

### plant_care

Người dùng hỏi về **kiến thức chăm cây** hoặc vấn đề sức khỏe của cây.

Ví dụ:

```txt
Tại sao lá cây bị vàng?
Lá cây bị úng thì cứu sao?
Cây tưới bao lâu một lần?
```

### cart_order

Người dùng muốn **thêm giỏ hàng / mua / đặt hàng**.

Ví dụ:

```txt
Thêm cây này vào giỏ.
Mua ngay sản phẩm này.
Đặt hàng giúp mình.
```

### general

Người dùng chỉ đang **chào hỏi hoặc hỏi chung chung**.

Ví dụ:

```txt
Xin chào.
Alo bạn ơi.
Bạn có thể giúp gì cho BigPlant?
```

### unclear

Câu hỏi quá mơ hồ, hệ thống chưa xác định được user muốn hỏi gì.

Ví dụ:

```txt
Giúp mình với.
Cái này ổn không?
```

---

## 4. Hệ thống nhận diện intent như thế nào

Đây là phần cốt lõi của app.

Hệ thống dùng **3 tầng nhận diện**.

```txt
Tầng 1: weighted rules
Tầng 2: semantic intent examples
Tầng 3: local LLM fallback when uncertain
```

Ba tầng này có vai trò khác nhau.

---

## 5. Tầng 1: weighted rules

### Mục đích

Tầng này dùng để bắt những câu có ý định rõ ràng bằng luật nhanh.

Ví dụ:

```txt
"bao nhiêu tiền"
"còn hàng không"
"thêm vào giỏ"
"tại sao lá cây bị vàng"
"xin chào"
```

### Nó hoạt động thế nào

Hệ thống có một danh sách các cụm từ/cấu trúc thường gặp cho từng intent.

Mỗi cụm từ được gán một trọng số.

Ví dụ về tư duy chấm điểm:

```txt
Nếu câu có "thêm vào giỏ" → cart_order được cộng điểm rất cao
Nếu câu có "bao nhiêu tiền" → product_info được cộng điểm cao
Nếu câu có "dễ chăm" → recommendation được cộng điểm
Nếu câu có "vàng lá" → plant_care được cộng điểm
Nếu câu có "xin chào" → general được cộng điểm
```

Sau đó hệ thống:

```txt
1. tính tổng điểm cho từng intent
2. xem intent nào cao nhất
3. so với intent đứng thứ hai
4. nếu điểm quá rõ thì chốt luôn
5. nếu chưa đủ rõ thì chuyển sang tầng semantic
```

### Tầng này để làm gì

```txt
- rất nhanh
- ít tốn tài nguyên
- tốt cho câu hỏi quen thuộc
- giúp không phải gọi embedding hoặc LLM trong mọi request
```

### Điểm yếu

```txt
- vẫn phụ thuộc vào marker/cụm từ
- không hiểu tốt các cách diễn đạt quá khác
```

---

## 6. Tầng 2: semantic intent examples

### Mục đích

Tầng này giúp hệ thống hiểu **câu tương tự về ý nghĩa**, ngay cả khi không dùng đúng marker.

Ví dụ:

```txt
shop còn mẫu này không
mình cần cây cho góc làm việc
lá cây bị úng thì cứu sao
alo bạn ơi
```

Những câu này có thể không trùng hoàn toàn với marker ở tầng rules, nhưng vẫn có ý định rõ.

### Nó hoạt động thế nào

Mỗi intent có một tập câu mẫu đại diện.

Ví dụ logic khái niệm:

```txt
product_info có các câu mẫu về giá, tồn kho, hình ảnh, độc tính sản phẩm
recommendation có các câu mẫu về tư vấn, chọn cây, nhu cầu không gian
plant_care có các câu mẫu về vàng lá, úng rễ, tưới nước
cart_order có các câu mẫu về mua ngay, thêm giỏ hàng
general có các câu mẫu chào hỏi
```

Khi user hỏi:

```txt
1. hệ thống embed câu hỏi đó
2. so với embedding của các câu mẫu
3. tính độ gần nghĩa giữa câu hỏi và từng nhóm intent
4. chọn intent có độ gần nghĩa cao nhất
5. nếu đủ chắc thì chốt luôn
6. nếu vẫn chưa đủ chắc thì mới sang tầng LLM fallback
```

### Tầng này để làm gì

```txt
- hiểu câu gần nghĩa tốt hơn rules
- không cần user gõ đúng từ khóa
- bắt được ngôn ngữ tự nhiên tốt hơn
- giảm số lần phải gọi local LLM
```

### Điểm mạnh nhất của tầng này

Đây là tầng giúp app hiểu được các câu như:

```txt
"shop còn mẫu này không" → product_info
"mình cần cây cho góc làm việc" → recommendation
"lá cây bị úng thì cứu sao" → plant_care
```

### Điểm yếu

```txt
- chậm hơn rules vì phải embed query
- vẫn có thể nhầm nếu các ví dụ intent chưa đủ tốt
```

---

## 7. Tầng 3: local LLM fallback

### Mục đích

Tầng này chỉ dùng khi hai tầng trước không đủ chắc chắn.

Tức là local LLM **không phải tầng mặc định của router**.

### Nó hoạt động thế nào

Nếu:

```txt
rules chưa chốt được
và semantic cũng chưa chốt được
```

thì hệ thống mới đưa câu hỏi cho local LLM dưới dạng bài toán phân loại intent.

LLM sẽ quyết định câu đó nên thuộc nhóm nào.

### Tầng này để làm gì

```txt
- xử lý các câu thật sự mơ hồ
- giữ độ linh hoạt cho hệ thống
- tránh việc rules và semantic đoán sai khi độ tự tin thấp
```

### Điểm yếu

```txt
- chậm nhất trong 3 tầng
- nếu model local chạy CPU thì tốn thời gian rõ rệt
```

---

## 8. Trước khi chốt intent, hệ thống extract gì từ câu hỏi

Ngoài việc đo intent, app còn rút ra một số thông tin từ câu hỏi để gửi cho handler xử lý tiếp.

Những thông tin này gồm:

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

### Ý nghĩa của các entity này

#### product_name

Tên sản phẩm/cây nếu câu hỏi nhắc trực tiếp.

Ví dụ:

```txt
Cây Aloe vera bao nhiêu tiền?
→ product_name = Aloe vera
```

#### max_price

Ngân sách sau khi đã được normalize về cùng currency với catalog.

Ví dụ:

```txt
dưới 400K → chuyển sang khoảng 16 USD nếu catalog đang dùng USD
$20 → giữ là 20 USD
```

#### care_level

Nếu user nói kiểu:

```txt
dễ chăm
hợp người mới
ít chăm
```

hệ thống có thể hiểu là đang tìm cây `easy`.

#### watering_need / light_requirement / placement

Đây là các gợi ý ngữ nghĩa để phục vụ recommendation.

Ngay cả khi DB chưa có field cứng tương ứng, app vẫn giữ các entity này để dùng ở semantic/vector layer.

#### pet_safe

Nếu câu hỏi liên quan đến mèo/chó/thú cưng thì app ghi nhận đây là câu hỏi an toàn/độc tính.

Entity này rất quan trọng với câu hỏi kiểu:

```txt
Cây này có độc với mèo không?
```

---

## 9. Flow chi tiết của từng intent

### 9.1. Product Info

#### Mục tiêu

Trả lời câu hỏi factual về **một sản phẩm cây cụ thể**.

#### Câu hỏi thường gặp

```txt
Cây Aloe vera bao nhiêu tiền?
Cây này còn hàng không?
Cây Jequirity bean có độc với mèo không?
Cho mình xem thông tin cây này.
```

#### Cách detect

Product Info thường được nhận diện từ:

```txt
giá
bao nhiêu tiền
còn hàng
tồn kho
size
hình ảnh
độc tính
an toàn với thú cưng
thông tin sản phẩm
```

Nếu user diễn đạt bằng câu gần nghĩa, semantic layer có thể bắt thay cho rules.

#### Luồng xử lý chi tiết

Khi intent = `product_info`, hệ thống làm như sau:

```txt
1. tìm product_name nếu có
2. thử tìm sản phẩm theo tên / slug / sku
3. nếu chưa thấy thì dò xem trong câu có nhắc một product cụ thể không
4. nếu vẫn không thấy thì hỏi lại user tên cây
5. nếu thấy product thì tải full product context
```

`Full product context` nghĩa là hệ thống sẽ gom đủ dữ liệu từ:

```txt
products
product_categories
product_variants
variant_inventory
product_images
plants
```

Sau đó hệ thống compute thêm:

```txt
price_min
price_max
price_text
available_qty
in_stock
primary_image_url
```

#### Product Info có dùng LLM không

Hiện tại:

```txt
Không dùng LLM để trả lời.
```

Lý do:

```txt
đây là factual flow
cần độ đúng cao
MongoDB đã có dữ liệu thật
tránh hallucination
tránh chậm
```

#### Câu hỏi độc tố ở Product Info được xử lý thế nào

Đây là điểm đặc biệt.

Khi câu hỏi có tín hiệu liên quan đến thú cưng hoặc độc tính, hệ thống **không dùng cùng kiểu trả lời với giá/tồn kho** nữa.

Ví dụ:

```txt
Cây Jequirity bean có độc với mèo không?
```

Lúc này app ưu tiên trả lời theo hướng:

```txt
1. kiểm tra plants.toxicity_warning
2. kiểm tra plants.safety_notes
3. xác định đây là câu hỏi về an toàn/độc tính
4. trả lời tập trung vào độc tính trước
```

Nghĩa là:

```txt
Nếu user hỏi độc tố,
app không nên mở đầu bằng giá/tồn kho,
mà phải mở đầu bằng kết luận an toàn/không an toàn.
```

Ví dụ hướng trả lời đúng:

```txt
Theo dữ liệu cây nền trong hệ thống, cây này có cảnh báo độc tính và không nên xem là an toàn cho mèo/chó.
```

#### Dữ liệu thật của Product Info lấy từ đâu

```txt
Tên, slug, sku, mô tả      → products
Giá                         → product_variants.price
Tồn kho                     → variant_inventory.available_qty
Ảnh                         → product_images
Độc tính / safety notes     → plants
Nhóm sản phẩm (Plants/Pots) → product_categories
```

---

### 9.2. Recommendation

#### Mục tiêu

Tư vấn cây phù hợp với nhu cầu user.

#### Câu hỏi thường gặp

```txt
Tôi muốn cây dễ chăm dưới 400K.
Mình cần cây cho góc làm việc.
Tôi muốn cây hợp người mới chơi.
Phòng ít nắng nên chọn cây gì?
```

#### Cách detect

Recommendation thường được nhận diện từ:

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

Nếu user dùng cách nói tự nhiên hơn như:

```txt
mình cần cây cho góc làm việc
mình muốn tìm một cây tặng sinh nhật
```

thì semantic layer sẽ hỗ trợ nhận diện intent này.

#### Luồng xử lý chi tiết

Khi intent = `recommendation`, hệ thống làm như sau:

```txt
1. lấy các filters đã extract
2. bỏ product_name nếu bị extract nhầm
3. tìm các candidate bằng hard filters trước
4. nếu query có tính semantic hoặc candidate ít thì bật vector search
5. merge kết quả filter cứng và vector search
6. rank candidate
7. lấy top 3
8. build câu trả lời deterministic
9. trả product cards
```

#### Hard filters hiện có thật trong app

Hiện app chỉ hard filter trên field có thật:

```txt
care_level
max_price
in_stock
```

Chi tiết nguồn dữ liệu:

```txt
care_level → products.care_level
max_price  → so với giá variant sau khi normalize currency
in_stock   → variant_inventory.available_qty
```

#### Semantic recommendation để làm gì

Semantic/vector search được dùng cho các nhu cầu như:

```txt
để bàn
ít nắng
thiếu sáng
phòng ngủ
phòng khách
làm quà
minimal
chill
```

Vì DB hiện tại chưa có đủ field cứng để filter hoàn toàn theo những nhu cầu này.

#### Recommendation có dùng LLM để trả lời không

Hiện tại:

```txt
Không dùng LLM để trả lời.
```

Lý do:

```txt
giữ tốc độ tốt hơn
giảm hallucination
recommendation hiện build deterministic text từ candidate thật
```

#### Recommendation dùng embedding thế nào

Khi app thấy câu recommendation mang tính ngữ nghĩa, nó sẽ:

```txt
1. embed câu query
2. search trên vector index của product
3. lấy product gần nghĩa nhất
4. query lại MongoDB để lấy dữ liệu thật mới nhất
5. mới đem đi rank và trả kết quả
```

Ý nghĩa của bước này:

```txt
vector search chỉ giúp tìm sản phẩm phù hợp theo nghĩa,
không phải nguồn sự thật cho giá hoặc tồn kho.
```

---

### 9.3. Plant Care

#### Mục tiêu

Trả lời câu hỏi về chăm cây, sức khỏe cây, bệnh cây.

#### Câu hỏi thường gặp

```txt
Tại sao lá cây bị vàng?
Lá cây bị úng thì cứu sao?
Cây tưới bao lâu một lần?
```

#### Cách detect

Plant Care thường được nhận diện từ:

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

Semantic layer hỗ trợ các câu như:

```txt
lá cây bị úng thì cứu sao
cách cứu cây sắp chết
```

#### Luồng xử lý chi tiết

Khi intent = `plant_care`, app làm như sau:

```txt
1. embed câu hỏi user
2. search vector trên knowledge base
3. nếu có context tài liệu thì build context
4. nếu local LLM available thì cho model trả lời dựa trên context
5. nếu model fail thì fallback bằng cách lấy đoạn context gần nhất
6. nếu không có knowledge phù hợp thì nói rõ chưa đủ tài liệu
```

#### Plant Care có dùng embedding không

```txt
Có.
```

#### Plant Care có dùng LLM không

```txt
Có, nhưng chỉ sau khi đã có context từ knowledge base.
```

Tức là:

```txt
LLM không tự bịa kiến thức plant care từ đầu.
LLM chỉ diễn giải sau khi đã có context phù hợp.
```

---

### 9.4. Cart Order

#### Mục tiêu

Nhận diện user muốn mua hoặc thêm giỏ.

#### Cách detect

Từ các cụm như:

```txt
thêm vào giỏ
giỏ hàng
đặt hàng
mua ngay
checkout
thanh toán
```

#### Luồng xử lý hiện tại

Hiện flow này mới chỉ dừng ở mức:

```txt
nhận diện đúng ý định
trả placeholder message
```

Nghĩa là:

```txt
app hiểu user muốn thao tác cart/order,
nhưng chưa nối Cart API thật trong chat flow.
```

---

### 9.5. General

#### Mục tiêu

Xử lý chào hỏi hoặc trò chuyện chung.

#### Cách detect

General thường được bắt từ:

```txt
xin chào
hello
hi
cảm ơn
```

Semantic layer hỗ trợ thêm các câu như:

```txt
alo bạn ơi
giúp mình với
```

#### Luồng xử lý hiện tại

General hiện có 2 nhánh:

##### Nhánh A: greeting ngắn

Nếu chỉ là câu ngắn kiểu:

```txt
xin chào
alo bạn ơi
hello
```

thì app trả deterministic greeting.

Mục đích:

```txt
nhanh hơn
tránh dùng LLM không cần thiết
tránh model sinh output rác
```

##### Nhánh B: general chat dài hơn

Nếu là câu general dài hơn, app sẽ:

```txt
1. gửi prompt cho local LLM
2. local LLM sinh câu trả lời
3. nếu fail thì fallback bằng static answer
```

#### General có dùng LLM không

```txt
Có, nhưng không phải mọi trường hợp đều dùng.
```

---

### 9.6. Unclear

#### Khi nào xảy ra

Khi app không tự tin người dùng đang muốn gì.

Ví dụ:

```txt
Giúp mình với
Cái này ổn không
```

#### Luồng xử lý

Nếu rules và semantic đều không đủ rõ,
app có thể thử LLM fallback để phân loại.

Nếu vẫn không rõ, app trả một câu hỏi mở để yêu cầu user nói rõ hơn.

Mục đích:

```txt
không đoán liều
ép user làm rõ ý định
```

---

## 10. Model LLM đang dùng trong app

App hiện hỗ trợ 3 model LLM local chính.

### 10.1. Model mặc định

Model mặc định hiện tại:

```txt
Qwen2.5-7B-Instruct Q4_K_M
```

### 10.2. Vì sao đang dùng Qwen2.5-7B làm mặc định

Điểm mạnh:

```txt
tiếng Việt ổn
instruction following tốt
general chat khá tự nhiên
ổn định cho vai trò router fallback + general chat + RAG answer
```

Điểm yếu:

```txt
nếu chạy CPU-only thì vẫn chậm
```

### 10.3. Meta-Llama-3.1-8B-Instruct

Điểm mạnh:

```txt
general chat tốt
reasoning tốt
câu trả lời tự nhiên
```

Điểm yếu:

```txt
tiếng Việt có thể không đều bằng Qwen trong một số tình huống
```

### 10.4. VinaLLaMA-7B-Chat

Điểm mạnh:

```txt
thiên về tiếng Việt
hợp để test hội thoại Việt
```

Điểm yếu:

```txt
cũ hơn
reasoning yếu hơn Qwen và Llama 3.1
tuân thủ instruction không tốt bằng Qwen
```

### 10.5. LLM hiện được dùng ở đâu trong app

Hiện local LLM được dùng ở 3 chỗ chính:

```txt
1. Router fallback khi rules + semantic không đủ chắc
2. General chat
3. Plant Care khi đã có knowledge context
```

Không dùng LLM cho:

```txt
Product Info factual
Recommendation factual
```

---

## 11. Embedding model đang dùng

Embedding model hiện tại:

```txt
BAAI/bge-m3
```

### 11.1. Vì sao dùng model này

Điểm mạnh:

```txt
đa ngôn ngữ
hỗ trợ tiếng Việt tốt
phù hợp semantic search và intent similarity
```

Điểm yếu:

```txt
phải load model nên request semantic đầu tiên sẽ chậm hơn
```

### 11.2. Embedding model đang được dùng ở đâu

Hiện tại embedding được dùng ở 3 luồng:

```txt
1. semantic router
2. recommendation vector search
3. plant care / RAG vector search
```

### 11.3. Embedding flow trong router

```txt
message
→ embed query
→ so với bộ câu mẫu của từng intent
→ chọn intent semantic gần nhất
```

### 11.4. Embedding flow trong recommendation

```txt
message có nhu cầu semantic
→ embed query
→ search product vector index
→ lấy danh sách product gần nghĩa
→ query MongoDB lại để lấy giá/tồn kho thật
```

### 11.5. Embedding flow trong plant care

```txt
message plant care
→ embed query
→ search knowledge vector index
→ lấy top chunks
→ build context
→ LLM diễn giải
```

---

## 12. Flow end-to-end của một câu hỏi

Tóm tắt cuối cùng, một câu hỏi đi qua hệ thống như sau:

```txt
Người dùng gửi câu hỏi
→ hệ thống normalize câu hỏi
→ extract entities
→ chấm intent bằng rules
→ nếu chưa chắc thì chấm bằng semantic examples
→ nếu vẫn chưa chắc thì dùng LLM fallback
→ xác định intent cuối cùng
→ chuyển sang nhánh xử lý tương ứng
→ query MongoDB / vector search / LLM theo đúng flow của intent đó
→ build response
→ trả về cho người dùng
```

Đây là logic thực thi thực tế của app hiện tại.
