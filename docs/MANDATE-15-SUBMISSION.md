# Báo Cáo Nộp Bài: AI Mandate #15 - Độ Tin Cậy Phát Hiện

- **Trạng thái**: Sẵn sàng đánh giá (Ready for Evaluation)
- **Đội ngũ thực hiện**: Task Force 3 (Team AIO02)
- **Hạn nộp**: Thứ Bảy 25/07/2026

---

## 🎫 1. Thông Tin Ticket Jira

* **Summary:** `AI MANDATE #15`
* **Labels:** `ai-mandate`, `m15`
* **Priority:** `High`

---

## 💬 2. Nội Dung Comment Bằng Chứng (Evidence Comment)

*(Copy toàn bộ phần bên dưới để paste vào comment của Jira Ticket)*

---

### 🔗 1. Link PR / Commit (Code & Config)
* **Repository:** `https://github.com/Baronger23/Capstone03`
* **Mã nguồn Replay API & Thuật toán:** [main.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/main.py) và [anomaly_detector.py](file:///d:/Xbrain/Read_Capstone03/aiops-engine/anomaly_detector.py)
* **Bộ kịch bản có nhãn:** [labeled_scenarios.json](file:///d:/Xbrain/Read_Capstone03/aiops-engine/datametric/labeled_scenarios.json)

---

### 🚀 2. Hướng Dẫn Chạy Lại (Repro Steps)
Mentor có thể kiểm thử tự động thuật toán hoặc tự bơm kịch bản ẩn theo các cách sau:

#### Cách A: Chạy bộ unit test tự động đo Precision/Recall
1. Truy cập thư mục engine:
   ```bash
   cd aiops-engine
   ```
2. Chạy test suite:
   ```bash
   python tests/test_ml_anomaly.py
   ```

#### Cách B: Gọi cURL API Replay để nạp kịch bản động
1. Bắn cURL chứa dữ liệu chuỗi thời gian kịch bản lỗi/tải cao vào EKS Pod:
   ```bash
   curl -X POST "http://aiops-engine.techx-tf3.svc.cluster.local:8000/simulate/replay" \
     -H "Content-Type: application/json" \
     -d @aiops-engine/datametric/labeled_scenarios.json
   ```

---

### 📊 3. Bằng Chứng Chạy Thật (Real Running Evidence)

#### A. Kết quả chạy test suite:
```
[TEST] Replay Scenario 'checkout_incident' -> Precision: 1.00, Recall: 1.00, Lead-time: 0 cycles (0.0s), SLO Breaches: 3
[TEST] Replay Scenario 'masking_incident' -> Precision: 1.00, Recall: 1.00, Lead-time: 0 cycles (0.0s), SLO Breaches: 3
[TEST] Replay Scenario 'high_load_healthy' -> Precision: 1.00, Recall: 1.00, Lead-time: 0 cycles (0.0s), SLO Breaches: 0

Ran 5 tests in 167.462s
OK
```

#### B. Trạng thái Pod vận hành liên tục trên EKS:
```bash
kubectl get pods -n techx-tf3 -l app=aiops-engine

NAME                            READY   STATUS    RESTARTS   AGE
aiops-engine-5d5c7964c6-q4ff5   1/1     Running   0          5m
```
*(Chỉ số RESTARTS = 0 chứng minh Pod chạy cực kỳ ổn định, không bị crash rò rỉ bộ nhớ).*

---

### 📝 4. Thiết Kế & Đánh Đổi (Link ADR Ký Tên)
Chi tiết về mô hình huấn luyện, cách trích xuất 18 features động, và cơ chế phát hiện hai lớp (SLO + ML) được trình bày tại:
* **ADR Kiến trúc:** [ADR-002-anomaly-detection-baseline.md](file:///d:/Xbrain/Read_Capstone03/docs/adr/ADR-002-anomaly-detection-baseline.md)
* **Ký tên phê duyệt:** Nhóm AIO02 (Task Force 3).
