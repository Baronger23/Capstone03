# 📊 BÁO CÁO ĐÁNH GIÁ MÔ HÌNH ISOLATION FOREST & ĐỀ XUẤT NÂNG CẤP (AIOPS ENGINE)

Tài liệu này ghi nhận kết quả huấn luyện, đánh giá mô hình **Isolation Forest (IF)** đối với các kịch bản kiểm thử nâng cao (SCN-A đến SCN-E) và đề xuất các giải pháp nâng cấp kỹ thuật tối ưu.

---

## 📈 Kết quả đánh giá Mô hình (Evaluation Metrics)

Mô hình đã được chạy huấn luyện trên 14 ngày dữ liệu baseline + Golden Cache và đánh giá trên tập Test chứa các kịch bản sự cố. Kết quả cụ thể:

| Dịch vụ (Service) | Kịch bản Kiểm thử | Precision | Recall | F1-Score | Trạng thái (F1 $\ge$ 0.77) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`frontend`** | **SCN-A** (Bảo trì / Node Drain) | 0.9921 | 0.9328 | **0.9615** | ✅ **PASSED** |
| **`checkout`** | **INC-1** (PostgreSQL Connection) | 0.9811 | 0.7743 | **0.8655** | ✅ **PASSED** |
| **`payment`** | **SCN-C** (Rò rỉ RAM âm thầm) | 0.9728 | 0.9328 | **0.9524** | ✅ **PASSED** |
| **`product-catalog`** | **SCN-E** (Mất gói tin mạng) | 0.9842 | 0.8134 | **0.8907** | ✅ **PASSED** |
| **`product-reviews`** | **SCN-B** (Spam AI / Prompt Inject) | 0.9799 | 1.0000 | **0.9898** | ✅ **PASSED** |
| **`shipping`** | **INC-5** (Kafka Consumer Lag) | 0.9851 | 0.6157 | **0.7577** | ❌ **FAILED (Recall < 0.70)** |
| **`recommendation`** | **SCN-D** (HTTP 4xx Security Scan) | 0.9834 | 0.9963 | **0.9898** | ✅ **PASSED** |

> **Điểm F1 trung bình toàn hệ thống:** **0.9154 (Đạt yêu cầu xuất sắc)**

---

## 🔍 Phân tích chi tiết Sự cố và Điểm nghẽn

### 1. Điểm sáng của mô hình (Successes)
* **SCN-A (Bảo trì / Node Drain) đạt F1 = 96.15%:** Cho thấy mô hình phân biệt rất tốt giữa biến động tải do bảo trì thông thường (không lỗi HTTP) và lỗi sập thật, hạn chế tối đa việc báo động giả lúc SRE đang thao tác.
* **SCN-B (Tấn công AI DoS) đạt F1 = 98.98%:** Việc kết hợp RPS + CPU + Latency giúp mô hình bắt cực nhạy các hành vi spam/tấn công LLM Gateway.
* **SCN-C (Rò rỉ RAM) đạt F1 = 95.24%:** Đặc trưng trích xuất **`memory_growth`** (tốc độ tăng trưởng RAM) đã phát huy tối đa tác dụng, giúp phát hiện xu hướng rò rỉ RAM rất sớm trước khi chạm ngưỡng OOM.

### 2. Điểm yếu cần nâng cấp (Failures)
* **Dịch vụ `shipping` (Kafka Consumer Lag) bị FAILED với Recall = 61.57%:**
  * **Nguyên nhân:** Lỗi nghẽn hàng đợi (Consumer Lag) diễn ra rất âm thầm ở tầng Queue. Nó không lập tức làm tăng vọt CPU/RAM của container hay gây lỗi HTTP (vì tin nhắn vẫn nằm trong hàng đợi chờ xử lý). Vì bộ 14 tính năng hiện tại đa phần tập trung vào các chỉ số HTTP (RPS, Latency, Error Rate) nên mô hình bị **bỏ sót 38.43% số mẫu lỗi (Low Recall)**.

---

## 🛠️ Đề xuất Giải pháp Nâng cấp Kỹ thuật (Upgrade Plan)

Để giải quyết triệt để điểm yếu của dịch vụ `shipping` và nâng chỉ số F1 toàn cụm lên $> 95\%$, chúng ta cần thực hiện các nâng cấp sau:

### Đề xuất 1: Bổ dung đặc trưng hàng đợi (Queue-aware Feature Engineering)
* **Nâng cấp:** Tích hợp thêm metric đo độ trễ hàng đợi từ Kafka vào mô hình.
* **Metric bổ sung:** `kafka_consumergroup_lag` (độ trễ tin nhắn).
* **Đặc trưng mới đề xuất:** `queue_lag_growth` (tốc độ tăng trưởng của lag).
* **Hiệu quả dự kiến:** Tăng Recall của kịch bản Kafka Lag trên dịch vụ `shipping` từ **61.57% lên >95%**.

### Đề xuất 2: Cấu hình tỷ lệ bất thường động cho từng Service (Service-specific Contamination)
* **Hiện tại:** Tất cả các service đều dùng chung tỷ lệ bất thường `contamination = 0.03`.
* **Nâng cấp:** Cấu hình tham số này động theo đặc thù của từng service:
  * Các service stateless, tải ổn định như `frontend`: đặt `contamination = 0.02` (giảm báo động rác).
  * Các service stateful, xử lý bất đồng bộ như `shipping`, `accounting` (chạy Kafka): tăng `contamination = 0.05` (tăng độ nhạy đối với các lỗi âm thầm).

### Đề xuất 3: Bổ sung chỉ số mạng chi tiết (Network Packet Drop Metrics)
* **Nâng cấp:** Đối với các lỗi mất gói tin mạng (**SCN-E**), thay vì dùng Latency làm proxy gián tiếp, chúng ta cần kéo metric `container_network_transmit_packets_dropped_total` hoặc tỷ lệ retry TCP.
* **Hiệu quả:** Giúp phát hiện tức thời các sự cố phần cứng/mạng ở tầng hạ tầng.
