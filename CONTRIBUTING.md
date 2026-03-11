# Contributing Guidelines

Chào mừng đến với dự án **Market Data Collection & Distribution System**.
Dự án được thiết kế chặt chẽ và yêu cầu các lập trình viên hoặc AI Agents phải tuân thủ nghiêm ngặt các quy chuẩn sau đây để đảm bảo codebase luôn thống nhất, hiệu năng cao và dễ bảo trì.

## 1. Cấu trúc thư mục
- `core/`: Chứa Domain models (Pydantic), entities và business rules. Không phụ thuộc vào các module khác.
- `api/`: Chứa FastAPI routers, controllers, dependency injections và RESTful endpoints.
- `db/`: Tương tác với TimescaleDB (connections, queries, repositories).
- `fetchers/`: Các worker/job hoặc websocket client lấy dữ liệu từ các sàn giao dịch.

## 2. Coding Conventions (BẮT BUỘC)

### 2.1. Type Hinting (Mypy Strict)
Hệ thống sử dụng **Type Hinting 100%**. Mọi function, class, data structure đều phải có Type Hinting rõ ràng. 
Cấu hình `mypy` đã được đặt ở độ khó cao nhất (`strict = true`). Cấm sử dụng `Any` nếu chưa qua suy xét cực kì kỹ lưỡng.

### 2.2. Formatting & Linting (Black + Ruff)
- **Công cụ**: Sử dụng `Black` để format code và `Ruff` để phân tích (linting).
- **Quy tắc**: Line-length giới hạn ở `88` ký tự.
- Code phải vượt qua `ruff check .` và `black --check .` trước khi merge. Không để lại `unused imports` hoặc code rác.

### 2.3. Models & Giao tiếp giữa các module
- Mọi dữ liệu trao đổi giữa các thành phần (`fetchers` nhận dữ liệu -> lưu vào `db` -> phân phối qua `api`) **BẮT BUỘC** phải gói gọn trong các Pydantic Models định nghĩa tại `core/models.py` (Ví dụ: `OHLCV` model). 
- Tuyệt đối không truyền dictionary (`dict`) hay tuple trực tiếp giữa các layers nhằm tránh mất kiểm soát về cấu trúc dữ liệu.

### 2.4. Docstring
- Function phức tạp và class phải có docstring giải thích tham số đầu vào và kiểu dữ liệu trả về. Mọi hàm cốt lõi phục vụ business logic đều cần giải thích ngắn gọn mục đích sử dụng.

## 3. Quy trình làm việc (Dành cho AI Agents)
- Luôn đọc file `pyproject.toml` để nắm bắt version thư viện.
- Nếu cần thêm thư viện/module, hãy hỏi ý kiến Lead (người dùng) trước khi cập nhật `pyproject.toml`.
- Tập trung vào tính module hoá (Modular). Tính tái sử dụng cao là ưu tiên hàng đầu.
