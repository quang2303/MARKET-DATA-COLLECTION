# 🚀 Hướng Dẫn Tích Hợp Cho Desktop App (Client Integration Guide)

Tài liệu này dành cho đội ngũ phát triển Desktop App (React Native, Flutter, Electron, C#, C++...) để hiểu và kết nối với hệ thống Backend thu thập dữ liệu thị trường.

---

## 1. Thông Tin Chung (General Info)

* **Base URL mặc định (Local)**: `http://127.0.0.1:8000`
* **Format Dữ liệu**: `application/json`
* **Xác thực (Authentication)**: Hiện tại API đang mở public, không yêu cầu JWT hoặc API Key ở header để đơn giản hóa quá trình phát triển. *(Sẽ cập nhật nếu có yêu cầu bảo mật).*

---

## 2. API Endpoints

### 2.1. Kiểm Tra Trạng Thái Server (Health Check)
Sử dụng endpoint này để Desktop App kiểm tra xem Backend đã khởi động và sẵn sàng nhận request hay chưa (ví dụ: hiển thị trạng thái "Connected" ở góc màn hình).

* **Method**: `GET`
* **Path**: `/health`
* **Response Thành công (200 OK)**:
  ```json
  {
    "status": "ok"
  }
  ```

---

### 2.2. Lấy Dữ Liệu Nến (Traditional Market Data Query)
Sử dụng endpoint này khi người dùng Desktop App thao tác bằng giao diện (chọn Symbol từ Dropdown, chọn Timeframe, chọn Ngày bắt đầu và kết thúc trên Calendar). Đây là cách gọi API truyền thống.

* **Method**: `GET`
* **Path**: `/api/v1/market-data`
* **Query Parameters (Bắt buộc)**:
  * `symbol` (string): Cặp giao dịch đang cần lấy (VD: `BTC/USDT`, `ETH/USDT`).
  * `timeframe` (string): Khung thời gian của nến (VD: `1m`, `1h`, `1d`).
  * `start_time` (string - ISO 8601): Thời gian bắt đầu (VD: `2024-01-01T00:00:00Z`).
  * `end_time` (string - ISO 8601): Thời gian kết thúc (VD: `2024-01-02T00:00:00Z`).

* **Ví dụ Request**:
  ```http
  GET http://127.0.0.1:8000/api/v1/market-data?symbol=BTC/USDT&timeframe=1h&start_time=2024-01-01T00:00:00Z&end_time=2024-01-02T00:00:00Z
  ```

* **Response Thành công (200 OK)**:
  Trả về một chuỗi (Array) các thanh nến (OHLCV). Desktop app có thể dùng List này đưa thẳng vào thư viện vẽ Biểu đồ (Charting Library).
  ```json
  [
    {
      "symbol": "BTC/USDT",
      "timestamp": "2024-01-01T00:00:00Z",
      "open": 42000.5,
      "high": 42150.0,
      "low": 41900.0,
      "close": 42100.0,
      "volume": 1250.5,
      "timeframe": "1h"
    },
    // ... các nến tiếp theo
  ]
  ```

---

### 2.3. Lấy Dữ Liệu Theo Câu Lệnh Tự Nhiên (Natural Language Query)
Sử dụng endpoint này khi Desktop App cung cấp một ô "Chatbox" hoặc "Thanh tìm kiếm thông minh" giống ChatGPT. Người dùng chỉ cần gõ yêu cầu bằng tiếng Anh/Việt, Backend sẽ tự dùng AI (Google Gemini) để hiểu và truy xuất dữ liệu trả về mảng nến y hệt như gọi `GET` thông thường.

* **Method**: `POST`
* **Path**: `/api/v1/query-by-text`
* **Headers**: `Content-Type: application/json`
* **Body Request**:
  ```json
  {
    "text": "Lấy giá BTC khung 1H trong 3 ngày qua"
  }
  ```
  *Lưu ý: Bạn có thể nhập tiếng Việt hoặc tiếng Anh ("Fetch BTC 1h candles for the last 3 days"), AI đều hiểu.*

* **Response Thành công (200 OK)**:
  Trả về Array OHLCV giống hệt với endpoint `GET /api/v1/market-data`. Bạn vẫn tiếp tục ném Response này vào thư viện vẽ Chart.
  ```json
  [
    {
      "symbol": "BTC/USDT",
      "timestamp": "2024-03-08T00:00:00Z",
      "open": 68000.0,
      "high": 68500.0,
      "low": 67800.0,
      "close": 68100.0,
      "volume": 3200.5,
      "timeframe": "1h"
    }
    // ...
  ]
  ```

---

## 3. Quản Lý Lỗi (Error Handling)

Khi có lỗi xảy ra (do truyền sai tham số, do DB sập, do hết hạn mức API AI), Backend sẽ trả về mã lỗi HTTP `>= 400` kèm theo JSON báo chi tiết lỗi:

* **HTTP 422 Unprocessable Entity**: Do Desktop Client truyền thiếu tham số (VD gọi GET mà mất đuôi `start_time`...).
* **HTTP 500 Internal Server Error**: Lỗi do quá trình xử lý Backend hoặc truy vấn Database thất bại.

**Cấu trúc JSON báo lỗi mặc định (FastAPI)**:
```json
{
  "detail": "Nội dung báo lỗi chi tiết sẽ nằm ở đây..."
}
```
**Hướng xử lý cho Desktop App:** Khi gọi API (fetch, axios, Dio...), hãy catch Status Code `>= 400`. Nếu bắt được, xin hãy parse trường `detail` ra và in lên màn hình (Snackbar / MessageBox) cho người dùng biết.

---

## 4. Kiến Nghị Luồng Xử Lý Dữ Liệu trên App (Suggested App Workflow)

1. **Khởi tạo Data Models**: Desktop Dev nên tạo class/struct `OHLCV` trên client giống hệt cấu trúc JSON trả về để parse dữ liệu tĩnh (statically typed).
2. **UX khi Fetching (LLM)**: Endpoint `POST /query-by-text` sẽ kết nối với Google Gemini, quá trình LLM suy luận sẽ mất **khoảng 1-3 giây**. Do đó, giao diện Desktop *bắt buộc* phải hiện Loading Indicator chờ đợi khi gọi POST này để UX không bị "đơ".
3. **Hiển thị Biểu đồ (Charting)**: Gợi ý sử dụng các package như `Lightweight Charts` (nếu dùng Web-view/Electron) hoặc native charting (như `fl_chart` trên Flutter, `LiveCharts` trên C# WPF) nhận đầu vào danh sách `(timestamp, open, high, low, close)`.
