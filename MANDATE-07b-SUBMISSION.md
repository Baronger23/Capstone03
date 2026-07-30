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
* **Script đo đạc đa dịch vụ minh bạch (No Warmup Trim):** [evaluate_mandate_7b_15.py](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/evaluate_mandate_7b_15.py)
* **Kết quả Benchmark đa dịch vụ JSON:** [multiservice_benchmark_results.json](https://github.com/Baronger23/Capstone03/blob/main/aiops-engine/datametric/multiservice_benchmark_results.json)

---

### 🛠️ 2. BẢNG CẬP NHẬT CÁC ĐIỂM ĐÃ SỬA CHỮA & HOÀN THIỆN (Fix & Remediation Log)

Đội ngũ phát triển đã rà soát và **hoàn thành 100% việc khắc phục các góp ý đánh giá**:

| STT | Vấn đề góp ý ban đầu | Trạng thái Đã sửa chữa | Chi tiết Giải pháp & Bằng chứng thực tế |
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

Mentor có thể kiểm thử toàn bộ luồng đo đạc minh bạch trên **7 microservices**:

```bash
kubectl --server=https://localhost:8443 --insecure-skip-tls-verify=true \
  exec deployment/aiops-engine -n techx-tf3 -- \
  python evaluate_mandate_7b_15.py
```

---

### 📊 4. Bối Cảnh Đo Đạc Minh Bạch (Evaluation Context & Disclosures)

- **Số lượng dịch vụ đo đạc**: **7 microservices** (`frontend`, `checkout`, `payment`, `product-catalog`, `product-reviews`, `shipping`, `recommendation`).
- **Tổng số chu kỳ Telemetry**: **420 chu kỳ** (30 phút liên tục).
- **Độ nhiễu tải cao thực tế (High Noise)**: RPS trung bình 80 req/s, Latency nền 45ms, CPU 35%.
- **Cửa sổ Warmup-trim**: **BỎ HOÀN TOÀN** (Đo đạc 100% dòng dữ liệu không cắt tỉa).

---

### 📐 5. Kết Quả Số Liệu Thực Tế & Vai Trò Hai Lớp (Multi-Layer Architecture)

#### 🅰️ Bảng So Sánh Chỉ Số Đơn Lớp ML vs Hệ Thống 2 Lớp (Combined):

| Chỉ số Metric | Isolation Forest Standalone (Thuần ML) | Combined 2-Layer System (ML + SLO Gate) | Ghi chú & Vai trò Kiến trúc |
|:---|:---:|:---:|:---|
| **Precision** | **7.12%** | **100.0%** | ML phát hiện nhạy; Cổng SLO lọc sạch báo động giả |
| **Recall** | **90.0%** | **90.0%** | Bắt trọn 9/10 giai đoạn sự cố thực tế |
| **False Positive Rate (FPR)** | **90.26%** | **0.00%** | Cổng SLO triệu tiêu toàn bộ 352 nhiễu giả |
| **Confusion Matrix (TP / FP / FN / TN)** | `27 / 352 / 3 / 38` | `27 / 0 / 3 / 390` | Động lực kết hợp 2 lớp hoàn hảo |

#### 🅱️ Phân Định Vai Trò Kiến Trúc Hai Lớp (Layer Value Proposition):

1. **Lớp 1 - ML Isolation Forest (Chủ động/Proactive)**:
   - Đóng vai trò bộ lọc độ nhạy cao (**High Sensitivity / High Recall = 90%**), quét đa chiều (CPU, Memory, Latency deviation, RPS delta) để phát hiện sự cố rò rỉ sớm trước khi chạm ngưỡng thảm họa.
2. **Lớp 2 - SLO Burn Rate & Health Gate (Chính xác/High Precision)**:
   - Đóng vai trò bộ lọc chính xác cao (**High Precision = 100%**), dùng công thức Burn Rate $K=14.4$ trên Span Metrics để triệt tiêu 352 cảnh báo nhiễu ngắn hạn, đưa tỷ lệ báo giả về **0.0%**.

---

### 📝 6. Thiết Kế & Đánh Đổi (ADR Signed)

Chi tiết thiết kế kiến trúc hai lớp phát hiện, RCA qua Jaeger Trace, và Human-in-the-Loop Slack Card được lưu tại:

* **Consolidated ADR:** [CONSOLIDATED_ADR.md](https://github.com/Baronger23/Capstone03/blob/main/docs/adr/CONSOLIDATED_ADR.md)
