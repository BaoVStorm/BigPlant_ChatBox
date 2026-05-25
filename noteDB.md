# BigPlant MongoDB Schema Notes

File này ghi chú cách hiểu schema DBML hiện tại khi triển khai trên MongoDB. DBML đang viết theo hướng PostgreSQL nên có các khóa như `user_id`, `category_id`, `product_id`, `variant_id`. Trong MongoDB, khóa chính của mỗi document là `_id`; các tên `*_id` trong DBML chỉ nên hiểu là khóa mẫu hoặc khóa tham chiếu.

## Quy Ước Chính

- Mỗi collection dùng `_id` làm khóa chính mặc định của MongoDB.
- Không query document chính bằng `product_id`, `category_id`, `plant_id`, `variant_id` nếu đó là khóa chính trong DBML. Trong MongoDB phải query bằng `_id`.
- Các field dạng tham chiếu vẫn có thể tồn tại, ví dụ `products.category_id`, `products.plant_id`, `product_variants.product_id`, `product_images.product_id`, `product_images.variant_id`. Các field này nên trỏ đến `_id` của collection liên quan.
- Source code nên hỗ trợ giá trị tham chiếu là `ObjectId`. Nếu dữ liệu cũ đang lưu string, code cần normalize được cả string và ObjectId trong giai đoạn chuyển đổi.
- Các field nghiệp vụ khác trong DBML được xem là đúng và nên giữ nguyên tên.

## Collections Cần Chú Ý Cho Chatbot

### `plants`

`plants` là nguồn thông tin thực vật học/cây nền, không phải sản phẩm bán hàng trực tiếp.

Các field chính:

- `_id`: khóa chính MongoDB, thay cho `plant_id` trong DBML.
- `scientific_name`: tên khoa học hiển thị chính thức.
- `scientific_name_search`: tên chuẩn hóa để search/matching/import.
- `common_name`: tên thường gọi.
- `family`, `taxonomic_order`, `genus`, `species`: thông tin phân loại.
- `taxonomic_status`: trạng thái tên loài, ví dụ accepted/synonym/ambiguous/unmatched/unknown.
- `uses`, `advantages`, `description`: mô tả, công dụng, ưu điểm.
- `toxicity_warning`: cảnh báo độc tính ngắn.
- `safety_notes`: ghi chú an toàn chi tiết hơn.
- `evidence_level`: mức bằng chứng của thông tin.
- `source`: nguồn dữ liệu.
- `created_at`, `updated_at`.

Quan hệ quan trọng:

- `products.plant_id` trỏ đến `plants._id`.
- `plant_aliases.plant_id` trỏ đến `plants._id`.
- `plant_distribution_areas.plant_id` trỏ đến `plants._id`.
- `plant_distribution_points.plant_id` trỏ đến `plants._id`.
- `scan_matches.plant_id` trỏ đến `plants._id`.

Ý nghĩa cho chatbot:

- Khi user hỏi cây có độc không, an toàn không, hoặc thông tin cây nền, nên lấy từ `plants.toxicity_warning` và `plants.safety_notes`, không tự bịa.
- Khi cần mô tả cây, có thể dùng `plants.description`, `uses`, `advantages`, nhưng phải cẩn thận với nội dung công dụng/y học và nên dựa vào `evidence_level`.
- Khi user dùng tên phổ thông hoặc tên alias, cần search thêm qua `plant_aliases`, không chỉ search `products.name`.

### `product_categories`

`product_categories` là cây danh mục sản phẩm.

Các field chính:

- `_id`: khóa chính MongoDB, thay cho `category_id` trong DBML.
- `parent_id`: trỏ đến `product_categories._id` nếu là danh mục con.
- `name`: tên danh mục.
- `slug`: slug duy nhất.
- `description`: mô tả danh mục.
- `is_active`: trạng thái hiển thị.
- `sort_order`: thứ tự sắp xếp.
- `created_at`, `updated_at`.

Quan hệ quan trọng:

- `products.category_id` trỏ đến `product_categories._id`.

Ý nghĩa cho chatbot:

- Dùng để lọc theo nhóm sản phẩm như cây, chậu, phụ kiện nếu category phản ánh cấu trúc shop.
- Khi gợi ý sản phẩm nên chỉ lấy category đang `is_active=true` nếu có join category.

### `products`

`products` là thông tin sản phẩm cha. Đây là nguồn chính cho tên, mô tả, slug, loại sản phẩm, rating và liên kết sang cây nền.

Các field chính:

- `_id`: khóa chính MongoDB, thay cho `product_id` trong DBML.
- `category_id`: trỏ đến `product_categories._id`.
- `plant_id`: trỏ đến `plants._id`.
- `sku`: mã sản phẩm cha, unique.
- `product_type`: plant/pot/accessory/service.
- `name`: tên sản phẩm hiển thị.
- `slug`: slug sản phẩm, unique.
- `short_description`: mô tả ngắn.
- `description`: mô tả chi tiết.
- `care_level`: mức chăm sóc.
- `rating_avg`, `rating_count`: dữ liệu đánh giá.
- `is_active`: trạng thái bán/hiển thị.
- `created_at`, `updated_at`.

Không nên giả định có các field này trong `products` nếu chưa thêm thật:

- `price_min`, `price_max`: giá phải tính từ `product_variants.price`.
- `stock`: tồn kho phải lấy từ `variant_inventory`.
- `pet_safe`: độ an toàn/thú cưng nên lấy từ `plants.toxicity_warning` hoặc `plants.safety_notes` nếu có.
- `light_requirement`, `watering_need`, `humidity_need`, `suitable_locations`, `suitable_for`, `tags`: các field này không có trong DBML hiện tại. Nếu chatbot cần filter cứng theo các tiêu chí này thì phải bổ sung field hoặc dùng vector search trên mô tả.

Quan hệ quan trọng:

- `products.category_id` → `product_categories._id`.
- `products.plant_id` → `plants._id`.
- `product_variants.product_id` → `products._id`.
- `product_images.product_id` → `products._id`.
- `product_reviews.product_id` → `products._id`.

Ý nghĩa cho chatbot:

- Product Info phải tìm sản phẩm bằng `products.name`, `products.slug`, `products.sku`, không dựa vào LLM đoán.
- Giá, size/options, tồn kho không nằm đủ trong `products`; phải join sang variants và inventory.
- Câu hỏi kiểu “Cây X bao nhiêu tiền?” cần lấy `products` + `product_variants` + `variant_inventory`.
- Câu hỏi kiểu “Cây X có độc với mèo không?” cần lấy `products` + `plants`.

### `product_variants`

`product_variants` là biến thể bán hàng của sản phẩm: size, chậu, option, giá.

Các field chính:

- `_id`: khóa chính MongoDB, thay cho `variant_id` trong DBML.
- `product_id`: trỏ đến `products._id`.
- `variant_sku`: mã biến thể, unique.
- `variant_name`: tên biến thể.
- `attributes`: object/json chứa thuộc tính linh hoạt, ví dụ size, pot_type, color nếu dữ liệu có.
- `price`: giá bán thật của biến thể.
- `compare_at_price`: giá gạch nếu có.
- `weight_gram`: khối lượng.
- `is_default`: biến thể mặc định.
- `is_active`: trạng thái biến thể.
- `created_at`, `updated_at`.

Không nên giả định có các field này ở cấp top-level nếu chưa có thật:

- `size`: nên đọc từ `attributes.size` hoặc `variant_name`.
- `pot_type`: nên đọc từ `attributes.pot_type` nếu có.
- `stock`: tồn kho nằm ở `variant_inventory`, không nằm trong `product_variants`.

Quan hệ quan trọng:

- `product_variants.product_id` → `products._id`.
- `variant_inventory.variant_id` → `product_variants._id`.
- `product_images.variant_id` → `product_variants._id`.
- `cart_items.variant_id` → `product_variants._id`.
- `order_items.variant_id` → `product_variants._id`.

Ý nghĩa cho chatbot:

- Giá sản phẩm nên trả theo range từ các active variants: min/max `price`.
- Nếu user hỏi “có mấy size/mấy loại”, dùng `variant_name` và `attributes`.
- Nếu user hỏi “còn hàng không”, phải join sang `variant_inventory`.

### `product_images`

`product_images` lưu ảnh theo sản phẩm hoặc theo biến thể.

Các field chính:

- `_id`: khóa chính MongoDB, thay cho `image_id` trong DBML.
- `product_id`: trỏ đến `products._id`, nullable nếu ảnh gắn riêng variant.
- `variant_id`: trỏ đến `product_variants._id`, nullable nếu ảnh gắn chung product.
- `image_url`: URL ảnh.
- `alt_text`: mô tả ảnh.
- `sort_order`: thứ tự hiển thị.
- `is_primary`: ảnh chính.
- `created_at`.

Ý nghĩa cho chatbot:

- Product card nên lấy ảnh `is_primary=true` trước, sau đó theo `sort_order`.
- Nếu user hỏi ảnh của một size/variant cụ thể, query theo `variant_id` trước rồi fallback về `product_id`.

### `variant_inventory`

`variant_inventory` là tồn kho theo biến thể.

Các field chính:

- `_id`: khóa chính MongoDB mặc định.
- `variant_id`: trỏ đến `product_variants._id`, nên unique vì mỗi variant có một inventory record.
- `available_qty`: số lượng có thể bán.
- `reserved_qty`: số lượng đang giữ.
- `sold_qty`: số lượng đã bán.
- `updated_at`.

Ý nghĩa cho chatbot:

- “Còn hàng không?” nên dựa vào `available_qty > 0`.
- Không lấy tồn kho từ `product_variants.stock` vì field này không thuộc DBML hiện tại.

## Implications Cho Source Code Chatbot

Product Info cần query theo flow:

```txt
products by name/slug/sku
→ product_categories by products.category_id
→ plants by products.plant_id
→ product_variants by product._id
→ variant_inventory by variant._id
→ product_images by product._id hoặc variant._id
```

Recommendation cần lưu ý:

- Filter `care_level` dùng `products.care_level`.
- Filter giá dưới X phải join `product_variants.price`, không dùng `products.price_min` nếu field chưa tồn tại.
- Filter còn hàng phải join `variant_inventory.available_qty`.
- Filter “để bàn”, “ít nắng”, “hay quên tưới”, “hợp phòng ngủ” hiện chưa có field cứng trong DBML. Có 2 hướng: bổ sung field có cấu trúc sau này, hoặc dùng vector search trên text từ `products.description`, `products.short_description`, `plants.description`, `plants.advantages`, `product_variants.attributes`.

Plant Care/RAG cần lưu ý:

- DBML hiện có `plants` nhưng chưa có collection bài viết chăm cây kiểu `plant_knowledge_articles`/`knowledge_chunks`.
- Nếu muốn RAG chăm cây đúng nghĩa, vẫn cần collection knowledge riêng hoặc dùng dữ liệu `plants.description/safety_notes` với phạm vi trả lời hạn chế.

Các mismatch hiện cần tránh trong code:

- Không dùng `product_id` làm khóa chính của product document; dùng `_id`.
- Không dùng `variant_id` làm khóa chính của variant document; dùng `_id`.
- Không dùng `products.price_min/price_max` nếu DB chưa có field này; tính từ variants.
- Không dùng `product_variants.stock`; lấy từ `variant_inventory`.
- Không dùng `products.pet_safe`; lấy độc tính/an toàn từ `plants.toxicity_warning` và `plants.safety_notes`.
- Không dùng `products.light_requirement/watering_need/suitable_locations` nếu DB chưa có field này.

# DB trong DBML
```js
// BigPlant - DBML for dbdiagram.io (PostgreSQL-oriented)
// Notes:
// - updated_at auto-update usually needs trigger/app-layer (DBML default only sets initial default). See docs/community notes.
// - Optional: If TableGroup is not supported in your plan, you can remove TableGroup blocks without affecting tables/refs.

Enum auth_provider {
  local
  google
}

Enum user_gender {
  male
  female
  other
  unknown
}

Enum otp_purpose {
  register_verify
  forgot_password
}

Enum otp_status {
  pending
  verified
  expired
  consumed
}

Enum cart_status {
  active
  converted
  abandoned
}

Enum order_status {
  pending_payment
  paid
  processing
  shipping
  completed
  cancelled
  refunded
}

Enum payment_method {
  cod
  vnpay
  momo
  stripe
  bank_transfer
  wallet
}

Enum payment_status {
  pending
  authorized
  captured
  failed
  cancelled
  refunded
  partially_refunded
}

Enum shipment_status {
  pending
  packed
  handed_over
  in_transit
  delivered
  failed
  returned
}

Enum product_type {
  plant
  pot
  accessory
  service
}

Enum inventory_tx_type {
  import
  reserve
  release
  deduct
  adjust
  return_in
  return_out
}

Enum scan_source {
  camera
  gallery
  api
}

Enum scan_status {
  success
  failed
  timeout
}

Enum match_source {
  ml_model
  manual_rule
  user_override
}

Table users {
  user_id bigserial [pk, increment]
  mongo_object_id varchar(48) [unique, note: 'legacy _id from mongodb']

  user_name varchar(100) [not null, unique]
  full_name varchar(120)

  email varchar(160) [not null, unique]
  phone_number varchar(20)

  password_hash varchar(255)

  date_of_birth date
  gender user_gender [not null, default: 'unknown']

  google_id varchar(100) [unique]
  provider auth_provider [not null, default: 'local']

  photo_url text
  score int [not null, default: 0, check: `score >= 0`]

  email_verified_at timestamptz
  is_active boolean [not null, default: true]
  last_login_at timestamptz

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (email)
    (phone_number)
    (created_at)
  }
}

Table user_notification_preferences {
  user_id bigint [pk, ref: - users.user_id]

  notify_deals boolean [not null, default: true]
  notify_plant_tips boolean [not null, default: true]
  language_code varchar(8) [not null, default: 'vi']

  updated_at timestamptz [not null, default: `now()`]
}

Table user_otps {
  otp_id bigserial [pk, increment]
  user_id bigint [ref: > users.user_id] // nullable for pre-user flows
  email varchar(160) [not null]

  purpose otp_purpose [not null]
  otp_code_hash varchar(255) [not null]
  status otp_status [not null, default: 'pending']

  resend_count int [not null, default: 0, check: `resend_count >= 0`]

  expires_at timestamptz [not null]
  verified_at timestamptz
  consumed_at timestamptz

  request_ip varchar(64)
  created_at timestamptz [not null, default: `now()`]

  indexes {
    (email, purpose, status)
    (user_id, purpose, created_at)
  }
}

Table addresses {
  address_id bigserial [pk, increment]
  user_id bigint [not null, ref: > users.user_id]

  recipient_name varchar(120) [not null]
  recipient_phone varchar(20) [not null]

  line1 varchar(255) [not null]
  line2 varchar(255)

  ward varchar(120)
  district varchar(120)
  city varchar(120) [not null]
  country varchar(80) [not null, default: 'VN']
  postal_code varchar(20)

  is_default boolean [not null, default: false]

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (user_id, is_default)
  }
}

Table product_categories {
  category_id bigserial [pk, increment]
  parent_id bigint [ref: > product_categories.category_id]

  name varchar(120) [not null]
  slug varchar(160) [not null, unique]
  description text

  is_active boolean [not null, default: true]
  sort_order int [not null, default: 0]

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]
}

Table products {
  product_id bigserial [pk, increment]
  category_id bigint [ref: > product_categories.category_id]
  plant_id bigint [not null, ref: > plants.plant_id]
  sku varchar(64) [not null, unique]
  product_type product_type [not null, default: 'plant']

  name varchar(180) [not null]
  slug varchar(220) [not null, unique]

  short_description varchar(255)
  description text
  care_level varchar(32)

  rating_avg numeric(3,2) [not null, default: 0, check: `rating_avg >= 0 AND rating_avg <= 5`]
  rating_count int [not null, default: 0, check: `rating_count >= 0`]

  is_active boolean [not null, default: true]

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (category_id, is_active)
    (name)
  }
}

Table product_variants {
  variant_id bigserial [pk, increment]
  product_id bigint [not null, ref: > products.product_id]

  variant_sku varchar(64) [not null, unique]
  variant_name varchar(120) [not null]

  attributes jsonb

  price numeric(12,2) [not null, check: `price >= 0`]
  compare_at_price numeric(12,2) [check: `compare_at_price IS NULL OR compare_at_price >= 0`]
  weight_gram int [check: `weight_gram IS NULL OR weight_gram >= 0`]

  is_default boolean [not null, default: false]
  is_active boolean [not null, default: true]

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (product_id, is_active)
    (price)
  }
}

Table product_images {
  image_id bigserial [pk, increment]
  product_id bigint [ref: > products.product_id]
  variant_id bigint [ref: > product_variants.variant_id]

  image_url text [not null]
  alt_text varchar(255)

  sort_order int [not null, default: 0]
  is_primary boolean [not null, default: false]

  created_at timestamptz [not null, default: `now()`]
}

Table variant_inventory {
  variant_id bigint [pk, ref: - product_variants.variant_id]

  available_qty int [not null, default: 0, check: `available_qty >= 0`]
  reserved_qty int [not null, default: 0, check: `reserved_qty >= 0`]
  sold_qty int [not null, default: 0, check: `sold_qty >= 0`]

  updated_at timestamptz [not null, default: `now()`]
}

Table inventory_transactions {
  inventory_tx_id bigserial [pk, increment]
  variant_id bigint [not null, ref: > product_variants.variant_id]

  tx_type inventory_tx_type [not null]
  quantity int [not null, check: `quantity > 0`]

  reference_type varchar(50)
  reference_id bigint

  note text
  created_by bigint [ref: > users.user_id]

  created_at timestamptz [not null, default: `now()`]

  indexes {
    (variant_id, created_at)
    (reference_type, reference_id)
  }
}

Table carts {
  cart_id bigserial [pk, increment]
  user_id bigint [not null, ref: > users.user_id]

  status cart_status [not null, default: 'active']

  subtotal_amount numeric(12,2) [not null, default: 0, check: `subtotal_amount >= 0`]
  discount_amount numeric(12,2) [not null, default: 0, check: `discount_amount >= 0`]
  shipping_amount numeric(12,2) [not null, default: 0, check: `shipping_amount >= 0`]
  total_amount numeric(12,2) [not null, default: 0, check: `total_amount >= 0`]

  expires_at timestamptz
  converted_to_order_id bigint

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (user_id, status)
    (expires_at)
  }
}

Table cart_items {
  cart_item_id bigserial [pk, increment]
  cart_id bigint [not null, ref: > carts.cart_id]
  variant_id bigint [not null, ref: > product_variants.variant_id]

  quantity int [not null, default: 1, check: `quantity > 0`]
  unit_price numeric(12,2) [not null, check: `unit_price >= 0`]
  line_total numeric(12,2) [not null, check: `line_total >= 0`]

  added_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (cart_id, variant_id) [unique]
  }
}

Table orders {
  order_id bigserial [pk, increment]
  order_code varchar(30) [not null, unique]

  user_id bigint [not null, ref: > users.user_id]
  cart_id bigint [ref: > carts.cart_id]

  shipping_address_id bigint [ref: > addresses.address_id]
  billing_address_id bigint [ref: > addresses.address_id]

  status order_status [not null, default: 'pending_payment']
  payment_status payment_status [not null, default: 'pending']

  subtotal_amount numeric(12,2) [not null, default: 0, check: `subtotal_amount >= 0`]
  discount_amount numeric(12,2) [not null, default: 0, check: `discount_amount >= 0`]
  shipping_amount numeric(12,2) [not null, default: 0, check: `shipping_amount >= 0`]
  tax_amount numeric(12,2) [not null, default: 0, check: `tax_amount >= 0`]
  total_amount numeric(12,2) [not null, default: 0, check: `total_amount >= 0`]

  note text

  placed_at timestamptz [not null, default: `now()`]
  paid_at timestamptz
  completed_at timestamptz
  cancelled_at timestamptz

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (user_id, created_at)
    (status, created_at)
  }
}

Table order_items {
  order_item_id bigserial [pk, increment]
  order_id bigint [not null, ref: > orders.order_id]
  variant_id bigint [not null, ref: > product_variants.variant_id]

  product_name_snapshot varchar(180) [not null]
  variant_name_snapshot varchar(120) [not null]

  unit_price numeric(12,2) [not null, check: `unit_price >= 0`]
  quantity int [not null, check: `quantity > 0`]
  line_total numeric(12,2) [not null, check: `line_total >= 0`]

  created_at timestamptz [not null, default: `now()`]

  indexes {
    (order_id, variant_id)
  }
}

Table payments {
  payment_id bigserial [pk, increment]
  order_id bigint [not null, ref: > orders.order_id]

  method payment_method [not null]
  status payment_status [not null, default: 'pending']

  amount numeric(12,2) [not null, check: `amount >= 0`]
  currency varchar(8) [not null, default: 'VND']

  provider varchar(60)
  provider_payment_id varchar(120)
  provider_raw jsonb

  authorized_at timestamptz
  captured_at timestamptz
  failed_at timestamptz

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (order_id)
    (provider, provider_payment_id) [unique]
  }
}

Table payment_transactions {
  payment_tx_id bigserial [pk, increment]
  payment_id bigint [not null, ref: > payments.payment_id]

  tx_type varchar(40) [not null]
  amount numeric(12,2) [not null, check: `amount >= 0`]

  provider_tx_id varchar(120)
  payload jsonb

  created_at timestamptz [not null, default: `now()`]

  indexes {
    (payment_id, created_at)
  }
}

Table shipments {
  shipment_id bigserial [pk, increment]
  order_id bigint [not null, ref: > orders.order_id]

  status shipment_status [not null, default: 'pending']

  carrier varchar(80)
  tracking_number varchar(120)

  shipped_at timestamptz
  delivered_at timestamptz

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (order_id)
    (tracking_number)
  }
}

Table shipment_events {
  shipment_event_id bigserial [pk, increment]
  shipment_id bigint [not null, ref: > shipments.shipment_id]

  event_code varchar(40) [not null]
  event_note text
  event_time timestamptz [not null]

  raw_payload jsonb
  created_at timestamptz [not null, default: `now()`]

  indexes {
    (shipment_id, event_time)
  }
}

Table product_reviews {
  review_id bigserial [pk, increment]
  product_id bigint [not null, ref: > products.product_id]
  user_id bigint [not null, ref: > users.user_id]

  order_item_id bigint [ref: > order_items.order_item_id]

  rating smallint [not null, check: `rating >= 1 AND rating <= 5`]
  comment text

  is_hidden boolean [not null, default: false]

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (product_id, created_at)
    (user_id, product_id) [unique]
  }
}

Table plants_old {
  plant_id bigserial [pk, increment]

  scientific_name varchar(180) [not null, unique]
  common_name varchar(180)

  family varchar(120)
  taxonomic_order varchar(120)
  genus varchar(120)
  species varchar(120)

  uses text
  advantages text
  description text

  source varchar(80)

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (common_name)
    (family)
    (genus)
  }
}

Table plants {
  plant_id bigserial [pk, increment]

  // Tên hiển thị chính thức trong app
  // Ví dụ: "Abrus precatorius"
  scientific_name varchar(180) [not null, unique]

  // Tên dùng để search / matching / import
  // Ví dụ: "abrus_precatorius"
  scientific_name_search varchar(180) [not null, unique]

  common_name varchar(180)

  family varchar(120)
  taxonomic_order varchar(120)
  genus varchar(120)
  species varchar(120)

  // accepted | synonym | ambiguous | unmatched | unknown
  taxonomic_status varchar(40)

  uses text
  advantages text
  description text

  // Cảnh báo độc tính ngắn, dùng để show trực tiếp trên app
  // Ví dụ: "Highly toxic seeds; not for self-medication."
  toxicity_warning text

  // Ghi chú an toàn chi tiết hơn
  safety_notes text

  // traditional_use | in_vitro | animal_study | human_trial | review | insufficient_evidence | unknown
  evidence_level varchar(60)

  // Giữ nguyên field source như bạn yêu cầu
  // Nhưng nên đổi từ varchar(80) sang text vì danh sách source sẽ dài
  // Thứ tự source map theo các field phía trên từ trên xuống dưới
  // Ví dụ:
  // "wiki,wiki,wiki,wiki,wiki,utp,pubmed,gbif,utp,pubmed,pubmed"
  source text

  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  indexes {
    (common_name)
    (family)
    (genus)
    (scientific_name_search)
    (taxonomic_status)
    (evidence_level)
  }
}

Table plant_aliases {
  alias_id bigserial [pk, increment]
  plant_id bigint [not null, ref: > plants.plant_id]

  alias_name varchar(180) [not null]
  lang_code varchar(8) [not null, default: 'vi']
  is_primary boolean [not null, default: false]

  indexes {
    (plant_id)
    (alias_name, lang_code)
  }
}

Table plant_distribution_areas {
  area_id bigserial [pk, increment]
  plant_id bigint [not null, ref: > plants.plant_id]

  area_name varchar(180) [not null]
  country_code varchar(8)

  indexes {
    (plant_id)
    (area_name)
  }
}

Table plant_distribution_points {
  point_id bigserial [pk, increment]
  plant_id bigint [not null, ref: > plants.plant_id]

  label varchar(180)

  latitude numeric(10,7) [not null, check: `latitude >= -90 AND latitude <= 90`]
  longitude numeric(10,7) [not null, check: `longitude >= -180 AND longitude <= 180`]

  indexes {
    (plant_id)
    (latitude, longitude)
  }
}

Table scan_requests {
  scan_id bigserial [pk, increment]
  user_id bigint [ref: > users.user_id]

  source scan_source [not null]

  image_url text
  image_sha256 char(64)

  status scan_status [not null]

  confidence numeric(5,4) [check: `confidence IS NULL OR (confidence >= 0 AND confidence <= 1)`]
  request_payload jsonb
  raw_response jsonb
  error_message text

  model_name varchar(100)
  model_version varchar(60)

  latency_ms int [check: `latency_ms IS NULL OR latency_ms >= 0`]

  created_at timestamptz [not null, default: `now()`]

  indexes {
    (user_id, created_at)
    (status, created_at)
    (image_sha256)
  }
}

Table scan_matches {
  scan_match_id bigserial [pk, increment]
  scan_id bigint [not null, ref: > scan_requests.scan_id]
  plant_id bigint [ref: > plants.plant_id]

  confidence numeric(5,4) [check: `confidence IS NULL OR (confidence >= 0 AND confidence <= 1)`]
  rank smallint [not null, default: 1, check: `rank >= 1`]

  source match_source [not null, default: 'ml_model']
  is_selected boolean [not null, default: true]

  created_at timestamptz [not null, default: `now()`]

  indexes {
    (scan_id, rank)
    (plant_id)
  }
}

// Optional (UI organization): bounded contexts
TableGroup auth_context {
  users
  user_notification_preferences
  user_otps
}

TableGroup shop_context {
  addresses
  product_categories
  products
  product_variants
  product_images
  variant_inventory
  inventory_transactions
  carts
  cart_items
  orders
  order_items
  payments
  payment_transactions
  shipments
  shipment_events
  product_reviews
}


Đọc kỹ cho tôi về phần DB này cho tôi, hãy nhớ thông tin các trường hiện tại đã đúng nhưng các thứ như (user_id, category_id, product_id, ...) chỉ là mẫu, db này tôi đang setup trên mongodb nên các trường này mặc định sẽ là _id (thay vì user_id hay product_id, ...) còn các trường khác thì đã đúng
Chú ý kỹ hơn với db sau: plants, products, product_categories, product_variants, product_images. Từ đó tạo cho tôi 1 file noteDB mô tả về db và hãy hiểu rõ hơn về chúng. (Mục tiêu cấu hình lại câu hỏi của source code và thông tin cần trả lời hiện tại chưa đúng với db)
```