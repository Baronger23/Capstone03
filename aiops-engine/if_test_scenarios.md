# 🧪 KỊCH BẢN KIỂM THỬ ISOLATION FOREST NÂNG CAO (AIOPS ENGINE)

Tài liệu này tổng hợp các kịch bản kiểm thử (Test Scenarios) nâng cao dành cho mô hình Máy học **Isolation Forest (IF)** của cụm TechX-Corp. Các kịch bản này được thiết kế dựa trên thực tế vận hành hệ thống Microservices trên EKS, kết hợp với các chỉ thị (**Mandates #3, #5, #6**) và lịch sử sự cố (**INC-1 đến INC-8**).

---

## 📊 Tổng quan các kịch bản Kiểm thử

| ID | Kịch bản Kiểm thử | Ràng buộc / Liên kết | Mục tiêu phát hiện của IF | Mức độ nghiêm trọng |
| :--- | :--- | :--- | :--- | :--- |
| **SCN-A** | Bảo trì trục xuất Pod / Drain Node | **Mandate #3** (Zero-Downtime) | Phân biệt bất thường tạm thời (Cold Start) với lỗi sụp đổ hệ thống thật. | Thấp (Transient Anomaly) |
| **SCN-B** | Tấn công Prompt Injection / Spam AI | **Mandate #6** (AI Trust & Safety) | Bắt lỗi quá tải tầng ứng dụng do spam đầu vào LLM Gateway. | Trung bình / Cao |
| **SCN-C** | Rò rỉ RAM âm thầm (Noisy Neighbor) | **Mandate #5** (Resource Limits) | Phát hiện rò rỉ dựa trên chỉ số tăng trưởng RAM (`memory_growth`). | Cao (Ngăn chặn OOM) |
| **SCN-D** | Tấn công rà quét bảo mật (HTTP 4xx Spam) | SRE Security Best Practices | Phân biệt lỗi Client (4xx) với lỗi sập Backend (5xx). | Thấp (Lưu ý bảo mật) |
| **SCN-E** | Nghẽn mạng chập chờn (Network Packet Loss) | SRE Network Performance | Phát hiện sụt giảm hiệu năng âm thầm (chỉ tăng Latency, không tăng lỗi). | Trung bình |

---

## 📝 Chi tiết các Kịch bản & Dữ liệu Metric giả lập

### 1. SCN-A · Bảo trì trục xuất Pod / Drain Node (Dựa trên Mandate #3)
> [!NOTE]
> **Mục tiêu chính:** Đánh giá tính kháng nhiễu (False Positive resistance) của mô hình khi hệ thống bảo trì định kỳ bình thường.

* **Bối cảnh:** SRE thực hiện rút node (`kubectl drain node`) để nâng cấp cụm. Pod của `frontend` bị tắt ở node cũ và khởi động lại trên node mới.
* **Hành vi biến đổi Metric:**
  * **RPS:** Sụt giảm tạm thời 20-30% trong vòng 1-2 phút (do mất đi 1 bản sao), sau đó tự phục hồi.
  * **CPU:** Tăng vọt nhẹ (Spike) trong lúc Pod mới chạy tiến trình khởi tạo (Warm-up).
  * **Latency P90:** Tăng nhẹ tức thời (từ 50ms lên 500ms) ở vài request đầu tiên do cache chưa được làm nóng, sau đó về lại mức bình thường.
  * **Error Rate:** Giữ nguyên bằng **0** (nhờ có cấu hình `readinessProbe` chuẩn chặn không cho traffic vào Pod khi chưa sẵn sàng).
* **Mục tiêu của IF:** Mô hình sẽ nhận diện đây là một trạng thái lệch baseline nhẹ (Anomaly Score tăng nhẹ) nhưng không vượt quá ngưỡng cảnh báo khẩn cấp, giúp SRE không bị báo động rác lúc bảo trì.

---

### 2. SCN-B · Tấn công Prompt Injection DoS / Spam AI (Dựa trên Mandate #6)
> [!WARNING]
> **Mục tiêu chính:** Phát hiện các hành vi lạm dụng tài nguyên LLM trước khi làm cạn kiệt ngân sách hoặc làm nghẽn dịch vụ AI.

* **Bối cảnh:** Kẻ tấn công gửi liên tục hàng loạt các prompt phức tạp hoặc mã độc chèn lệnh (Prompt Injection) vào tính năng tóm tắt review nhằm mục đích làm nghẽn dịch vụ `product-reviews` và proxy LLM.
* **Hành vi biến đổi Metric:**
  * **RPS:** Vọt lên gấp **5 - 10 lần** bình thường trên dịch vụ `product-reviews`.
  * **CPU:** Spikes lên **>90%** do CPU phải bận rộn lọc PII, lọc inject và xử lý chuỗi văn bản lớn.
  * **Latency P90:** Vọt lên cực cao **>5 giây** vì LLM phải xử lý và sinh chuỗi phản hồi quá dài.
  * **Error Rate:** Có thể tăng nhẹ nếu Bedrock API trả về HTTP 429 (Too Many Requests).
* **Mục tiêu của IF:** Bắt trọn sự kết hợp bất thường của bộ ba: **RPS cực cao + CPU cực cao + Latency cực cao** tại một dịch vụ duy nhất để kích hoạt cảnh báo lưu lượng độc hại.

---

### 3. SCN-C · Rò rỉ RAM âm thầm - Noisy Neighbor (Dựa trên Mandate #5)
> [!IMPORTANT]
> **Mục tiêu chính:** Phát hiện lỗi cạn kiệt tài nguyên trước khi hệ thống bị sập hoàn toàn.

* **Bối cảnh:** Một Pod mới được deploy nhưng cấu hình giới hạn tài nguyên bị để trống (Vi phạm Mandate #5) và gặp lỗi rò rỉ bộ nhớ (memory leak). RAM của Pod tăng dần theo thời gian, bắt đầu tranh chấp và ngốn sạch RAM của node vật lý.
* **Hành vi biến đổi Metric:**
  * **Memory:** Chỉ số `memory_usage` tăng tuyến tính không ngừng qua từng giờ. Đặc trưng trích xuất **`memory_growth`** liên tục mang giá trị dương lớn qua nhiều chu kỳ liên tiếp.
  * **CPU / RPS / Latency:** Ban đầu hoàn toàn bình thường ở mức tối ưu.
* **Mục tiêu của IF:** Phát hiện sớm lỗi rò rỉ dựa trên đặc trưng tốc độ tăng trưởng bộ nhớ (`memory_growth`) để SRE có thể can thiệp trước khi Pod bị Kernel kích hoạt cơ chế OOM-Killer giết chết đột ngột.

---

### 4. SCN-D · Tấn công rà quét bảo mật / HTTP 4xx Spam
> [!TIP]
> **Mục tiêu chính:** Tránh restart nhầm các dịch vụ lành mạnh khi lỗi bắt nguồn từ phía người dùng/kẻ tấn công.

* **Bối cảnh:** Kẻ tấn công hoặc các bot quét lỗ hổng (vulnerability scanner) gửi hàng loạt yêu cầu truy cập các đường dẫn không tồn tại nhằm rà quét hệ thống, sinh ra lượng lớn mã HTTP `404 Not Found` hoặc `403 Forbidden`.
* **Hành vi biến đổi Metric:**
  * **RPS:** Tăng vọt đột biến.
  * **Error Rate:** Tăng vọt lên rất cao, nhưng phân tích chi tiết mã trạng thái cho thấy chủ yếu là **HTTP 4xx** (không phải 5xx).
  * **CPU / RAM / Latency:** Hoàn toàn ổn định trong vùng an toàn.
* **Mục tiêu của IF:** Phân loại đúng loại lỗi. IF cần nhận diện đây là hành vi spam của client và không kích hoạt hành động khôi phục hạ tầng (remediation restart) vì backend hoàn toàn khỏe mạnh.

---

## 5. SCN-E · Nghẽn mạng chập chờn / Mất gói tin (Network Packet Loss)
> [!CAUTION]
> **Mục tiêu chính:** Phát hiện các sự cố suy giảm hiệu năng âm thầm (Silent Performance Degradation) không phát sinh log lỗi.

* **Bối cảnh:** Đường truyền mạng giữa `frontend` và dịch vụ xử lý backend (ví dụ: `product-catalog`) gặp sự cố chập chờn, tỷ lệ mất gói tin (packet loss) dao động ở mức 10-15%.
* **Hành vi biến đổi Metric:**
  * **RPS:** Sụt giảm nhẹ do các request phải chờ phản hồi và thực hiện cơ chế retry.
  * **Latency P90:** Vọt lên cực cao (từ 50ms vọt lên **2.5 - 4.0 giây**) do độ trễ truyền gói tin và thời gian chờ retransmission.
  * **Error Rate:** Vẫn xấp xỉ bằng **0** vì sau khi retry, các request cuối cùng vẫn thành công (chỉ bị chậm).
* **Mục tiêu của IF:** Nhận diện sự bất thường khi **RPS giảm đi kèm Latency tăng vọt** dù hệ thống không phát sinh bất kỳ lỗi HTTP 5xx hay log exception nào.
