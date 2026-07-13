# 📖 AIOPS ENGINE: KIẾN TRÚC THUẬT TOÁN & HƯỚNG DẪN VẬN HÀNH

Tài liệu này cung cấp cái nhìn chi tiết về các giải thuật SRE/AIOps được triển khai trong hệ thống **AIOps Engine**, các phân tích đánh đổi (trade-offs), và hướng dẫn từng bước để triển khai vận hành từ khi clone dự án về máy.

---

## 🛠️ 1. TỔNG QUAN HỆ THỐNG & SƠ ĐỒ ĐIỀU PHỐI (CMDR)

Hệ thống hoạt động theo mô hình khép kín tự động: **Detect (Phát hiện) ──► Diagnose (Chẩn đoán) ──► Decide (Quyết định) ──► Act (Khắc phục)**.

```mermaid
graph TD
    subgraph Layer 1: SLO Burn-Rate (Critical)
        A1[Multi-window Burn Rate] -->|Breach| B[Trigger RCA Pipeline]
    end
    subgraph Layer 2: Z-Score (Warning)
        A2[Dynamic Rolling Z-Score] -->|Breach| SlackLog[Slack Alert Only]
    end
    B --> C[Step 1: Jaeger Trace Analyzer]
    C --> D[Step 2: Drain3 Log Clusterer]
    D --> E[Step 3: Bedrock LLM Diagnostician]
    E --> F[Step 4: Remediation Safety Check]
    F -->|Approved| G[Execute K8s Action]
```

---

## 📊 2. CHI TIẾT CÁC THUẬT TOÁN GIÁM SÁT 2 LỚP

Hệ thống chia làm hai lớp giám sát độc lập bổ trợ cho nhau:

### 2.1 LỚP 1: THUẬT TOÁN SLO BURN-RATE (SEVERITY: CRITICAL)
Lớp này chịu trách nhiệm phát hiện lỗi ảnh hưởng trực tiếp đến trải nghiệm người dùng dựa trên tốc độ tiêu thụ Quỹ lỗi (Error Budget).

* **Công thức toán học**:
  $$\text{Burn Rate} = \frac{\text{Current Error Rate (5m / 1h)}}{\text{Allowed Error Rate (1\%)}} $$
  * Với SLO thành công $99\%$, Quỹ lỗi cho phép là $1\%$ trong 30 ngày (720 giờ).
  * **Burn-rate = 14.4**: Tốc độ đốt cháy hết toàn bộ quỹ lỗi 30 ngày chỉ trong vòng **50 giờ**.
* **Giải thuật đa cửa sổ (Multi-Window)**:
  * Hệ thống chỉ phát cảnh báo khi **cả cửa sổ ngắn (5 phút) và cửa sổ dài (1 giờ)** đều có Burn-rate $> 14.4$.
  * **Mục đích**: Cửa sổ 5m giúp phát hiện lỗi tức thì, cửa sổ 1h đảm bảo lỗi đó kéo dài tích lũy đủ lớn chứ không phải là nhiễu mạng chập chờn tự hết.
* **Phân tích Đánh đổi (Trade-off)**:
  * 👍 **Ưu điểm**: Miễn dịch hoàn toàn với hiện tượng đầu độc dữ liệu lịch sử (Poisoning) vì ngưỡng cam kết $1\%$ lỗi là tuyệt đối. Không có cảnh báo giả cho lỗi thoáng qua.
  * 👎 **Nhược điểm**: Có độ trễ nhất định (tối đa 5 phút) để tích lũy dữ liệu trước khi kích hoạt sửa lỗi.

---

### 2.2 LỚP 2: THUẬT TOÁN DYNAMIC ROLLING Z-SCORE (SEVERITY: WARNING)
Lớp này chịu trách nhiệm giám sát độ lệch chuẩn của các chỉ số hạ tầng (CPU, RAM, DB connection pool, Network latency) để cảnh báo sớm nguy cơ.

* **Công thức toán học**:
  $$Z_t = \frac{x_t - \mu}{\sigma}$$
  * $x_t$: Giá trị metric hiện tại.
  * $\mu$ (Mean) & $\sigma$ (Stddev): Được tính cuộn trượt trên cửa sổ **7 ngày qua** bằng PromQL.
* **Cơ chế thiết kế baseline**:
  * Để tối ưu hóa hiệu năng tính toán PromQL và đơn giản hóa việc triển khai trong Tuần 1, hệ thống tính toán giá trị trung bình cộng ($\mu$) và độ lệch chuẩn ($\sigma$) trực tiếp bằng các hàm `avg_over_time` và `stddev_over_time` trên Prometheus.
* **Phân tích Đánh đổi (Trade-off)**:
  * 👍 **Ưu điểm**: Phát hiện bất thường cực nhạy ngay cả trong giờ thấp điểm (độ lệch chuẩn co lại). Giúp SRE chủ động xử lý sớm trước khi vỡ SLO.
  * 👎 **Nhược điểm**: Dễ bị cảnh báo giả (False Positive) khi có tải tăng đột biến tự nhiên. Do đó, lớp này **chỉ cảnh báo Warning lên Slack, không cấp quyền tự động sửa lỗi**.

---

## 🔍 3. GIẢI THUẬT TRUY VẾT LỖI (TRACE RCA & LOG CLUSTERING)

Khi Lớp 1 bị kích hoạt, hệ thống sẽ thực hiện thu thập bằng chứng:

### 3.1 THUẬT TOÁN TRUY VẾT TOPOLOGY (JAEGER TRACE)
1. Lấy mã **Trace ID** của request bị lỗi từ Prometheus alert.
2. Gọi API của **Jaeger Query** để lấy toàn bộ danh sách các cuộc gọi (Spans) của Trace đó.
3. Duyệt cây đồ thị (Call Tree) từ trên xuống dưới:
   * Tính toán thời gian xử lý (duration) của từng node.
   * Tìm dịch vụ sâu nhất bị trả về mã lỗi HTTP 5xx hoặc gRPC Error Status $\neq 0$.
   * Xác định node đó là **Thủ phạm gốc (Culprit Service)**.

### 3.2 THUẬT TOÁN GOM CỤM NHẬT KÝ (DRAIN3 LOG CLUSTERING)
1. Khi đã tìm ra Thủ phạm gốc (ví dụ: `product-catalog`), hệ thống truy vấn kho log tập trung (OpenSearch/Elasticsearch) để lấy toàn bộ log thô của service đó trong cửa sổ 5 phút qua.
2. Áp dụng thuật toán **Drain3 (Fixed-depth prefix tree)**:
   * Tự động loại bỏ các tham số động thay đổi liên tục (như IDs, IPs, Timestamps).
   * Gom các dòng log thô có cấu trúc giống nhau thành một **Template mẫu** (ví dụ: `database connection timeout to host *`).
   * Đếm tần suất xuất hiện của từng template để tìm ra dòng log lỗi có tần suất đột biến nhất làm bằng chứng.

---

## 🚀 4. HƯỚNG DẪN VẬN HÀNH PIPELINE TỪ A-Z

Khi clone dự án này về máy, bạn thực hiện chạy hệ thống theo các bước sau:

### BƯỚC 1: THIẾT LẬP KẾT NỐI MẠNG (PORT-FORWARD TUNNEL)
Mở 2 cửa sổ Terminal độc lập trên máy của bạn và chạy các lệnh sau để mở luồng kết nối tới EKS Cluster:

* **Terminal 1: Mở cổng kết nối ứng dụng & Jaeger UI**
  ```powershell
  kubectl -n techx-tf3 port-forward svc/frontend-proxy 8080:8080
  ```
* **Terminal 2: Mở SSM Tunnel kết nối AWS (Chỉ chạy trên Windows)**
  ```powershell
  $env:PATH += ";C:\Program Files\Amazon\SessionManagerPlugin\bin"
  # (Tiến hành chạy lệnh ssm tunnel của bạn để kết nối EKS)
  ```

---

### BƯỚC 2: CẤU HÌNH THÔNG TIN MÔI TRƯỜNG (.ENV)
Tạo file **`aiops-engine/.env`** và điền đầy đủ cấu hình AWS Bedrock cá nhân để gọi mô hình **Amazon Nova Micro**:

```bash
# Model ID sử dụng thế hệ mới siêu nhanh siêu rẻ của AWS
BEDROCK_MODEL_ID=amazon.nova-micro-v1:0

# Thông tin Access Key tài khoản AWS cá nhân chứa Credit của bạn
EXTERNAL_AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
EXTERNAL_AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
EXTERNAL_AWS_REGION=us-east-1

# Slack integration webhook URL (Nhận card chẩn đoán)
SLACK_WEBHOOK_URL=YOUR_SLACK_WEBHOOK_URL
```

---

### BƯỚC 3: KHỞI ĐỘNG MÁY CHỦ CỤC BỘ (LOCAL SERVER)
Mở Terminal 3, di chuyển vào thư mục dự án và khởi động máy chủ FastAPI:

```powershell
# Di chuyển vào thư mục engine
cd aiops-engine

# Kích hoạt server uvicorn
./venv/Scripts/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### BƯỚC 4: KÍCH HOẠT BÀI TEST CHẨN ĐOÁN
Để kiểm tra xem hệ thống chẩn đoán AI và bắn thẻ Slack hoạt động chuẩn xác hay chưa, bạn mở Terminal 4 và chạy lệnh giả làm Alertmanager gửi webhook:

```powershell
# Chạy file giả lập bắn webhook sự cố
aiops-engine/venv/Scripts/python aiops-engine/fire_webhook.py
```

* **Kết quả mong đợi**:
  * Log của Uvicorn hiện thông báo `LLM Diagnosis success`.
  * Slack của bạn nổ Card màu cam/đỏ chứa đầy đủ thông tin RCA có dẫn chứng chi tiết kèm nút duyệt hành động sửa lỗi.
