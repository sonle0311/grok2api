# Tích hợp Grok2API vào dự án khác

Tài liệu dành cho backend ứng dụng cần gọi chat, tạo ảnh và video qua Grok2API. Bản xuất ngày 12/10/2026, từ commit `05b0c53e`. Tài khoản đang sử dụng là Grok Web Heavy; các chức năng âm thanh cần tài khoản Console khả dụng.

## 1. Địa chỉ và API key

Gateway hiện chạy tại `http://127.0.0.1:8000`. Base URL cho SDK OpenAI là `http://127.0.0.1:8000/v1`.

1. Đăng nhập giao diện quản trị.
2. Mở **Client Keys / Khóa API** tại `/client-keys`.
3. Tạo khóa, bật các model cần dùng và đặt giới hạn RPM, đồng thời, thời hạn nếu cần.
4. Sao chép khóa vào biến môi trường của backend dự án tích hợp.

```dotenv
GROK2API_BASE_URL=http://127.0.0.1:8000/v1
GROK2API_API_KEY=g2a_REPLACE_WITH_YOUR_CLIENT_KEY
```

Mọi endpoint suy luận dùng header:

```http
Authorization: Bearer g2a_REPLACE_WITH_YOUR_CLIENT_KEY
```

API key này là khóa khách của gateway. Không dùng mật khẩu admin, JWT admin hoặc token SSO Grok để gọi `/v1/*`. Giữ khóa trong backend; frontend của dự án khác nên gọi backend của chính dự án đó.

Nếu dự án khác chạy trong Docker Desktop, dùng `http://host.docker.internal:8000/v1` và kiểm tra Docker có kết nối được dịch vụ Windows đang nghe trên loopback không. Nếu không, cần cấu hình gateway lắng nghe trên địa chỉ Docker truy cập được. Với máy khác, `127.0.0.1` là máy của bên gọi; cần địa chỉ mạng của máy gateway hoặc tên miền HTTPS và cấu hình lắng nghe tương ứng. Bản hiện tại chỉ nghe `127.0.0.1:8000`.

## 2. Model và quyền sử dụng

Danh sách thực sự gọi được phải lấy bằng khóa khách:

```bash
curl "$GROK2API_BASE_URL/models" \
  -H "Authorization: Bearer $GROK2API_API_KEY"
```

Phản hồi có dạng OpenAI: `{"object":"list","data":[{"id":"..."}]}`. Dùng chính xác `data[].id`; danh sách còn phụ thuộc tài khoản khả dụng, quota và quyền của khóa.

Các tên dưới đây thuộc danh mục Grok Web của bản xuất, không phải cam kết mọi thời điểm đều gọi được:

| Nhu cầu | Model |
| --- | --- |
| Chat nhanh | `grok-chat-fast` |
| Chat tự động | `grok-chat-auto` |
| Chat chuyên sâu | `grok-chat-expert` |
| Chat Heavy | `grok-chat-heavy` |
| Tạo ảnh | `grok-imagine-image-lite`, `grok-imagine-image`, `grok-imagine-image-2.0` |
| Sửa ảnh | `grok-imagine-image-edit` |
| Tạo video | `grok-imagine-video` |

Tên công khai có thể được đổi trong Model Routes. Tên có namespace `Web/`, `Build/`, `Console/` dùng để ghim provider khi route tương ứng tồn tại; lấy tên từ giao diện hoặc `/v1/models`, không tự ghép tên rồi giả định tồn tại.

| Chức năng | Build | Web | Console |
| --- | --- | --- | --- |
| Chat | Có | Có, theo hạng tài khoản | Có |
| Tạo và sửa ảnh | Không | Có | Có |
| Video | Tài khoản Super/trả phí | Có | Có |
| TTS, STT, Realtime | Không | Không | Có |

Hỗ trợ trong gateway không đồng nghĩa tài khoản có quyền hoặc quota. Subscription Heavy không tự chuyển quota Web thành quota Console.

## 3. Chat bằng Python

Cài SDK OpenAI trong dự án tích hợp, rồi dùng:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["GROK2API_BASE_URL"],
    api_key=os.environ["GROK2API_API_KEY"],
    timeout=180.0,
    max_retries=0,
)

response = client.chat.completions.create(
    model="grok-chat-heavy",
    messages=[
        {"role": "system", "content": "Trả lời bằng tiếng Việt."},
        {"role": "user", "content": "Viết một đoạn giới thiệu sản phẩm."},
    ],
    stream=False,
)
print(response.choices[0].message.content)
```

Với hội thoại nhiều lượt, gửi lại lịch sử `messages`. Streaming dùng `stream=True`; đọc từng `choices[0].delta.content` nếu có. Không coi HTTP 200 là kết thúc thành công nếu luồng bị ngắt trước sự kiện kết thúc.

## 4. Chat bằng JavaScript phía server

Ví dụ dùng `fetch` có sẵn trong Node.js:

```javascript
const base = process.env.GROK2API_BASE_URL.replace(/\/$/, "");
const key = process.env.GROK2API_API_KEY;

async function request(path, body) {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(180_000),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text}`);
  return JSON.parse(text);
}

const result = await request("/chat/completions", {
  model: "grok-chat-heavy",
  messages: [{ role: "user", content: "Xin chào" }],
  stream: false,
});
console.log(result.choices[0].message.content);
```

Đặt khóa trong môi trường của server. Không đưa đoạn có khóa vào bundle chạy trong trình duyệt.

## 5. Responses và Anthropic Messages

`POST /v1/responses` nhận JSON:

```json
{
  "model": "grok-chat-heavy",
  "input": "Tóm tắt lợi ích của năng lượng mặt trời.",
  "store": false,
  "stream": false
}
```

Đọc văn bản ở các phần tử `output[].content[]` có `type: "output_text"`. Khả năng lưu phiên, compact và `previous_response_id` phụ thuộc provider; khi tích hợp ban đầu nên dùng `store:false` và tự quản lý lịch sử.

`POST /v1/messages` nhận:

```json
{
  "model": "grok-chat-heavy",
  "max_tokens": 1024,
  "messages": [{"role": "user", "content": "Xin chào"}],
  "stream": false
}
```

Phản hồi Messages chứa `content[]`; nội dung văn bản có `type:"text"`. Chat, Responses và Messages trả cấu trúc giao thức trực tiếp, không có lớp bọc `data` giống Admin API.

## 6. Tạo ảnh và sửa ảnh

Gửi `POST /v1/images/generations`:

```json
{
  "model": "grok-imagine-image-2.0",
  "prompt": "Một quán cà phê Việt Nam buổi sáng, ánh sáng tự nhiên",
  "n": 1,
  "aspect_ratio": "16:9",
  "response_format": "url"
}
```

Đọc URL từ `data[0].url`. Nếu URL là đường dẫn tương đối, nối với origin của gateway. `response_format:"b64_json"` trả dữ liệu ảnh Base64 ở `data[].b64_json`.

Trên Web, lựa chọn sản phẩm ảnh phụ thuộc tên model. `resolution` và `quality` dành cho generation không chọn chất lượng trên Web; dùng `grok-imagine-image-2.0` theo danh mục route. Bắt đầu với `n:1`.

Sửa ảnh bằng `POST /v1/images/edits` với JSON:

```json
{
  "model": "grok-imagine-image-edit",
  "prompt": "Đổi màu chiếc ghế thành màu đen",
  "image": {"url": "https://your-domain.example/input.png"},
  "n": 1,
  "response_format": "url"
}
```

URL nguồn cần được hệ thống tải ảnh truy cập được. Không dùng đường dẫn tệp trên máy của ứng dụng làm URL.

## 7. Tạo video và lấy kết quả

Video là tác vụ bất đồng bộ. Dùng `POST /v1/videos/generations`, không dùng `/v1/videos` như một số SDK khác.

```json
{
  "model": "grok-imagine-video",
  "prompt": "Máy bay giấy bay qua thành phố lúc hoàng hôn",
  "duration": 8,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

`duration` là số giây nguyên, từ 1 đến 15 ở endpoint generation của bản này; giới hạn provider/tài khoản có thể thấp hơn. Dùng trường `duration`, không dùng bí danh `seconds`. Phản hồi tạo tác vụ:

```json
{"request_id":"video_example"}
```

Poll `GET /v1/videos/video_example` bằng cùng khóa đã tạo tác vụ:

- `pending`: đang xử lý; chờ vài giây rồi kiểm tra lại.
- `done`: lấy `video.url`.
- `failed`: đọc `error.code` và `error.message`, dừng poll.

Ví dụ nối tiếp hàm `request` ở phần JavaScript:

```javascript
const job = await request("/videos/generations", {
  model: "grok-imagine-video",
  prompt: "Sóng biển lúc bình minh",
  duration: 8,
  aspect_ratio: "16:9",
  resolution: "720p",
});

const deadline = Date.now() + 10 * 60_000;
let completed = false;
while (Date.now() < deadline) {
  await new Promise(resolve => setTimeout(resolve, 5_000));
  const state = await request(`/videos/${encodeURIComponent(job.request_id)}`);
  if (state.status === "failed") throw new Error(JSON.stringify(state.error));
  if (state.status === "done") {
    console.log(state.video.url);
    completed = true;
    break;
  }
}
if (!completed) throw new Error(`Hết thời gian chờ; giữ request_id ${job.request_id} để kiểm tra tiếp`);
```

Giữ `request_id` trong database dự án tích hợp để tiếp tục poll sau khi tiến trình khởi động lại. Không tự tạo lại video chỉ vì poll hết thời gian.

`GET /v1/videos/{request_id}/content` yêu cầu client key. URL tài nguyên công khai `/v1/media/videos/{asset_id}` có thể mở trực tiếp; bảo vệ URL này như đường dẫn có quyền truy cập. Nếu frontend không thể gửi Authorization tới content endpoint, backend ứng dụng nên tải/proxy video cho người dùng đã được phép.

Image-to-video có thể thêm `image:{"url":"https://your-domain.example/input.png"}`. Chỉnh sửa và kéo dài video qua `/v1/videos/edits`, `/v1/videos/extensions` yêu cầu route Console `grok-imagine-video`; chưa dùng được chỉ với tài khoản Web Heavy.

## 8. Âm thanh khi bổ sung Console

Các endpoint dưới đây cần route Console có quyền và quota:

| Method | Endpoint | Nội dung |
| --- | --- | --- |
| POST | `/v1/audio/speech` | TTS tương thích OpenAI, trả bytes âm thanh |
| POST | `/v1/audio/transcriptions` | STT từ file hoặc URL |
| GET | `/v1/tts/voices` | Danh sách giọng |
| GET WebSocket | `/v1/realtime` | Hội thoại realtime |

Ví dụ TTS:

```json
{
  "model": "grok-voice-latest",
  "input": "Xin chào",
  "voice": "alloy",
  "response_format": "mp3"
}
```

Chọn model và giọng theo route/danh sách thực tế. Response speech là nhị phân; ghi vào tệp âm thanh, không gọi `response.json()`.

## 9. Lỗi và retry

| HTTP | Cách xử lý |
| --- | --- |
| 400 | Kiểm tra model, tên trường và giới hạn tham số |
| 401 | Kiểm tra client key, thời hạn và header Bearer |
| 403 | Kiểm tra quyền khóa và lỗi upstream; lỗi Cloudflare cần xử lý ở gateway |
| 404 | Kiểm tra endpoint, model route hoặc request_id |
| 429 | Chờ theo Retry-After nếu có; giảm tốc độ và đồng thời |
| 5xx | Đọc lỗi, kiểm tra provider, kết nối, quota và log gateway |

Lưu status HTTP, body lỗi và request ID nếu có. Chỉ retry có giới hạn cho thao tác phù hợp. Không retry mù yêu cầu tạo ảnh/video hoặc lời gọi tool có tác dụng phụ: upstream có thể đã nhận yêu cầu trước khi kết nối bị ngắt.

## 10. Vận hành gateway

- `GET /healthz` kiểm tra tiến trình; `GET /readyz` cho biết trạng thái từng thành phần. HTTP 200 của readyz vẫn có thể đi kèm `state:"degraded"`.
- FlareSolverr cục bộ: `http://127.0.0.1:8191`; chế độ Web hiện là FlareSolverr. Docker cần hoạt động để cookie được làm mới.
- Khi chuyển gateway sang máy khác, cấu hình lại FlareSolverr, mạng và API key; không sao chép cookie rồi mặc định nó dùng được với IP khác.
- Cấu hình Public API Base URL trong gateway thành origin/prefix mà ứng dụng tích hợp truy cập được để URL ảnh/video không trỏ sai về localhost.
- Gói này không chứa mật khẩu, SSO, client key thật hoặc database.

## 11. OpenAPI và nguồn tham khảo

`openapi.json` đi kèm là bản Swagger 2.0 xuất từ `backend/docs/swagger.json` của cùng commit. Có thể nhập vào Postman hoặc công cụ hỗ trợ Swagger 2.0. Tài liệu giao diện `/docs` và handler hiện tại cần được đối chiếu nếu schema Swagger thiếu chi tiết.

Nguồn trong repository: `README.md`, `frontend/src/features/docs/api-docs-page.tsx`, các handler tại `backend/internal/transport/http/inference/`. Tài liệu trực tuyến của bản chạy: `http://127.0.0.1:8000/docs`.
