# Báo Cáo Nộp Bài: AI Mandate #7b - Chạy Thật + Đo Đạc Minh Bạch (Proactive ML Detection & RCA)

- **Trạng thái**: Sẵn sàng đánh giá (Ready for Evaluation)
- **Đội ngũ thực hiện**: Task Force 3 (Team AIO02)
- **Hạn nộp**: Thứ Bảy 25/07/2026

---

## 🎫 1. Thông Tin Ticket Jira

* **Summary:** `AI MANDATE #7b`
* **Labels:** `ai-mandate`, `m7`
* **Priority:** `High`

---

## 💬 2. Nội Dung Comment Bằng Chứng (Evidence Comment)

*(Copy toàn bộ phần bên dưới để paste vào comment của Jira Ticket)*

---

### 🔗 1. Link PR / Commit (Code & Config)

* **Repository:** `https://github.com/Baronger23/Capstone03`
* **Proactive ML Loop + Slack Approval endpoint:** [main.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/main.py)
* **Thuật toán Isolation Forest + SLO Burn Rate:** [anomaly_detector.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/anomaly_detector.py)
* **LLM Chẩn đoán nguyên nhân gốc (RAG Playbooks):** [llm_diagnostician.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/llm_diagnostician.py)
* **Slack Interactive Card (Approve/Reject):** [slack_notifier.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/slack_notifier.py)
* **Script đo đạc đa dịch vụ minh bạch (No Warmup Trim):** [evaluate_mandate_7b_15.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/evaluate_mandate_7b_15.py)
* **Kết quả Benchmark đa dịch vụ JSON:** [multiservice_benchmark_results.json](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/datametric/multiservice_benchmark_results.json)

---

### 🛠️ 2. BẢNG KHẮC PHỤC TRIỆT ĐỂ THEO GÓP Ý ĐÁNH GIÁ CỦA MENTOR (Fix & Remediation Log)

Đội ngũ phát triển đã rà soát và **hoàn thành 100% việc khắc phục các góp ý đánh giá**:

| STT | Yêu cầu Góp ý của Mentor | Trạng thái Đã sửa chữa | Chi tiết Giải pháp & Bằng chứng minh bạch |
| :-: | :--- | :---: | :--- |
| **1** | Bị đẩy Precision/Recall = 1.0 do đo 1 service + cắt warmup | ✅ **ĐÃ KHẮC PHỤC 100%** | Đo đạc trên **7 microservices**, thêm nhiễu nền tải cao (RPS 80, Latency 45ms), **bỏ hoàn toàn warmup-trimming** (đo 420/420 chu kỳ). |
| **2** | Cổng validation_passed báo pass ảo do miễn trừ Precision | ✅ **ĐÃ KHẮC PHỤC 100%** | Gỡ bỏ 100% logic miễn trừ (exempt). Công khai minh bạch Precision thuần ML (**7.12%**) và lý do cần Lớp 2 SLO Gate. |
| **3** | Model IsolationForest flag tràn lan, chưa rõ vai trò ML vs SLO | ✅ **ĐÃ KHẮC PHỤC 100%** | Làm rõ kiến trúc 2 Lớp: **Lớp ML** đóng vai trò quét nhạy phát hiện rò rỉ sớm (**Recall 90%**), **Lớp SLO** đóng vai trò lọc báo động giả (**Precision 100%**). |
| **4** | Kịch bản Masking bị lộ (kích cả 3 cổng cùng lúc) | ✅ **ĐÃ KHẮC PHỤC 100%** | Dựng kịch bản **Masking thực tế** trên `checkout`: Latency nhích nhẹ 120ms + CPU rò rỉ chậm (lỗi ẩn dưới baseline trôi, chưa sập SLO ngay). |
| **5** | 0% Báo giả đo trên fixture latency=0/error=0 ảo | ✅ **ĐÃ KHẮC PHỤC 100%** | Đo đạc tỷ lệ báo giả (FPR = 0.00%) trên **tải cao có nhiễu thực tế** từ 7 microservices. |
| **6** | Headline P/R chưa ghi rõ bối cảnh đo đạc | ✅ **ĐÃ KHẮC PHỤC 100%** | Cập nhật báo cáo ghi rõ bối cảnh 7 microservices, 420 chu kỳ, tải nhiễu RPS 80. |
| **7** | Lỗi Engine kẹt Z=999.0 trên Production | ✅ **ĐÃ KHẮC PHỤC 100%** | Sửa `main.py` gọi đúng `check_service_anomaly`, sửa `anomaly_detector.py` PromQL đa nhãn EKS, sửa `remediation_handler.py` luồng verify 5 phút. |

---

### 🚀 3. Hướng Dẫn Chạy Lại Đánh Giá (Repro Steps)

> **Yêu cầu:** Cần SSM Tunnel đang chạy (Port 8443 mở) để kết nối vào EKS private cluster.

#### Bước 0 — Mở SSM Tunnel (giữ terminal này mở suốt quá trình test)

```bash
aws ssm start-session --target i-0f5959afa0eb31e7c \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"ADA05FFC84146C0AED730F78786EB320.gr7.ap-southeast-1.eks.amazonaws.com\"],\"portNumber\":[\"443\"],\"localPortNumber\":[\"8443\"]}"
```

#### Bước 1 — Chạy bộ Evaluator đa dịch vụ minh bạch (Không cắt warmup, có nhiễu nền thực tế)

```bash
python aiops-engine/evaluate_mandate_7b_15.py
```

---

### 📊 4. BẰNG CHỨNG THỰC NGHIỆM TRỰC TIẾP TRÊN EKS CLUSTER & MINH BẠCH ĐA DỊCH VỤ

Đội ngũ đã kích hoạt kịch bản thực tế trên cụm EKS `techx-corp-tf3` trong namespace `techx-tf3`.

#### 📸 Ảnh 1 — Trạng thái Pod EKS chạy ổn định (RESTARTS = 0):

![Pod status - 1/1 Running, RESTARTS=0](screenshot/Pod%20status.png)

*(Pod `aiops-engine` đang ở trạng thái `1/1 Running`, RESTARTS = 0, hoạt động ổn định liên tục)*

---

#### 📸 Ảnh 2 — Log Pod: Luồng quét chủ động Isolation Forest chạy thật với Log Pred=1/-1:

![Log Pod - Proactive Scan ML](screenshot/Log%20Pod%20.png)

*(Log ghi nhận toàn bộ luồng chủ động: `SLO is stable` → Engine quét ML proactive → `[ML Scan] Service 'checkout': pred=-1 (Anomaly), score=0.6420` → `[ML Scan] Service 'payment': pred=1 (Normal)`)*

---

#### 📸 Ảnh 3 — Thẻ tương tác Approve/Reject trên Slack (Human-in-the-Loop):

![Slack Card - AIOps Incident Alert với nút Approve/Reject](screenshot/Slack.png)

*(Kênh `#alert-aiops`: AIOps Bot gửi thẻ cảnh báo gồm phân tích đường đi lỗi RCA, chẩn đoán chi tiết Bedrock LLM, Jaeger Trace ID, lệnh khắc phục đề xuất `kubectl scale`, và 2 nút tương tác `✅ Approve (Duyệt chạy)` / `❌ Reject (Từ chối)` — Human-in-the-Loop hoàn chỉnh)*

---

### 📐 5. KẾT QUẢ ĐO ĐẠC MINH BẠCH ĐA DỊCH VỤ (PRECISION / RECALL / FPR)

Báo cáo số liệu đo đạc thực tế trên **7 Microservices** (`frontend`, `checkout`, `payment`, `product-catalog`, `product-reviews`, `shipping`, `recommendation`) với **420 chu kỳ Telemetry**, có nhiễu nền tải cao (RPS 80, Latency 45ms), **không cắt tỉa Warmup-trim**:

#### 🅰️ Bảng So Sánh Chỉ Số Đơn Lớp ML vs Hệ Thống 2 Lớp (Combined):

| Chỉ số Metric | Isolation Forest Standalone (Thuần ML) | Combined 2-Layer System (ML + SLO Gate) | Ghi chú & Vai trò Kiến trúc |
|:---|:---:|:---:|:---|
| **Precision** | **7.12%** | **100.0%** | ML phát hiện nhạy; Cổng SLO lọc sạch 352 báo động giả |
| **Recall** | **90.0%** | **90.0%** | Bắt trọn 9/10 giai đoạn sự cố thực tế |
| **False Positive Rate (FPR)** | **90.26%** | **0.00%** | Cổng SLO triệu tiêu toàn bộ 352 nhiễu giả |
| **True Positives (TP)** | `27` | `27` | Phát hiện chính xác thời điểm rò rỉ |
| **False Positives (FP)** | `352` | `0` | Lớp SLO triệt tiêu 100% cảnh báo giả |
| **False Negatives (FN)** | `3` | `3` | Sự cố bị bỏ sót |
| **True Negatives (TN)** | `38` | `390` | Trạng thái bình thường được xác nhận đúng |

#### 🅱️ Phân Định Vai Trò Kiến Trúc Hai Lớp (Layer Value Proposition):

1. **Lớp 1 - ML Isolation Forest (Chủ động/Proactive)**:
   - Đóng vai trò bộ lọc độ nhạy cao (**High Sensitivity / High Recall = 90%**), quét đa chiều (CPU, Memory, Latency deviation, RPS delta) để phát hiện sự cố rò rỉ sớm trước khi chạm ngưỡng thảm họa.
2. **Lớp 2 - SLO Burn Rate & Health Gate (Chính xác/High Precision)**:
   - Đóng vai trò bộ lọc chính xác cao (**High Precision = 100%**), dùng công thức Burn Rate $K=14.4$ trên Span Metrics để triệt tiêu 352 cảnh báo nhiễu ngắn hạn, đưa tỷ lệ báo giả về **0.0%**.

---

### 📝 6. Thiết Kế & Đánh Đổi (Link ADR Ký Tên)

Chi tiết về thiết kế hai lớp phát hiện (ML + SLO Burn Rate), luồng RCA qua Jaeger Trace, gọi Bedrock LLM RAG Playbooks, và cơ chế Human-in-the-Loop Slack card được ghi nhận tại:

* **ADR Kiến trúc tổng hợp:** [CONSOLIDATED_ADR.md](https://github.com/Baronger23/Capstone03/blob/main/docs/adr/CONSOLIDATED_ADR.md)
* **Ký tên phê duyệt:** Nhóm AIO02 (Task Force 3).
